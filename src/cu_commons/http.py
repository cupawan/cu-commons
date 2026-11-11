"""JSON over HTTP with timeouts and retries on rate limits / server errors."""
import logging
import time

import requests

from cu_commons.errors import ApiError

logger = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


def request_json(method: str, url: str, *, retries: int = 3, backoff: float = 1.5, timeout: float = 30,
                 session: requests.Session | None = None, **kwargs):
    """Return decoded JSON (or None for empty bodies). Retries 429/5xx and connection errors."""
    http = session or requests
    for attempt in range(1, retries + 1):
        try:
            response = http.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as e:
            if attempt == retries:
                raise ApiError(f"{method} {url} failed: {e}") from e
            time.sleep(backoff ** attempt)
            continue
        if response.status_code in RETRY_STATUS and attempt < retries:
            wait = float(response.headers.get("Retry-After") or backoff ** attempt)
            logger.warning("%s %s -> %s, retrying in %.1fs", method, url, response.status_code, wait)
            time.sleep(min(wait, 60))
            continue
        if response.status_code >= 400:
            raise ApiError(f"{method} {url} -> {response.status_code}: {response.text[:300]}", response.status_code)
        return response.json() if response.content else None
    raise ApiError(f"{method} {url} failed after {retries} attempts")
