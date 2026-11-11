"""AWS Lambda entry-point wrapper: SSM secrets, logging, error alerts, event typing."""
import functools
import json
import logging
import os

from cu_commons.errors import NoDataError

logging.getLogger().setLevel(logging.INFO)


def event_kind(event: dict) -> str:
    """'schedule' (EventBridge / our own schedule payloads), 'http' (API Gateway), or 'unknown'."""
    if event.get("source") == "schedule" or event.get("detail-type") == "Scheduled Event":
        return "schedule"
    if "body" in event or "requestContext" in event:
        return "http"
    return "unknown"


def lambda_handler(service: str, alerter=None, ssm_prefix: str | None = None):
    """Decorator. Loads SSM parameters (ssm_prefix, or env SSM_PREFIX), reports exceptions to `alerter`
    (default: TelegramAlerter.from_env()), treats NoDataError as a notice, and returns HTTP-style dicts."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(event, context):
            log = logging.getLogger(service)
            prefix = ssm_prefix or os.environ.get("SSM_PREFIX")
            if prefix:
                from cu_commons.config import load_ssm

                load_ssm(prefix)
            alert = alerter
            if alert is None:
                from cu_commons.alerts import TelegramAlerter

                alert = TelegramAlerter.from_env()
            try:
                result = fn(event, context)
                return result if result is not None else {"statusCode": 200, "body": "OK"}
            except NoDataError as e:
                log.warning("%s", e)
                if alert:
                    alert.notify(f"[{service}] {e}")
                return {"statusCode": 200, "body": str(e)}
            except Exception as e:
                log.exception("unhandled error")
                if alert:
                    alert.error(service, e, {"event_kind": event_kind(event)})
                return {"statusCode": 500, "body": json.dumps({"error": type(e).__name__})}

        return wrapper

    return decorator
