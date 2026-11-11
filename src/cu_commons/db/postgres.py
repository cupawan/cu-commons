"""Postgres client (works with any Postgres; tuned for Neon serverless).

Give it the connection string as shown by your provider, e.g.
``postgresql://user:pass@host/db?sslmode=require``. TLS is on unless ``sslmode=disable``.
Neon scales idle databases to zero, so the first connection is retried with backoff.
"""
import logging
import os
import ssl
import time
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlsplit, urlunsplit

logger = logging.getLogger(__name__)
RETRYABLE = ("OperationalError", "InterfaceError")


def normalize_url(raw: str) -> tuple[str, bool]:
    """Return (SQLAlchemy pg8000 URL, use_tls). Drops libpq-only query parameters."""
    parts = urlsplit(raw)
    sslmode = dict(parse_qsl(parts.query)).get("sslmode", "require")
    return urlunsplit(("postgresql+pg8000", parts.netloc, parts.path, "", "")), sslmode != "disable"


class Postgres:
    def __init__(self, url: str, connect_timeout: int = 10, retries: int = 4):
        if not url:
            raise ValueError("Postgres URL is required")
        self.url, self.tls = normalize_url(url)
        self.connect_timeout, self.retries = connect_timeout, retries
        self._engine = None

    @classmethod
    def from_env(cls, var: str = "PostgresUrl", **kwargs):
        return cls(os.environ.get(var, ""), **kwargs)

    @property
    def engine(self):
        if self._engine is None:
            from sqlalchemy import create_engine

            args = {"timeout": self.connect_timeout}
            if self.tls:
                args["ssl_context"] = ssl.create_default_context()
            self._engine = create_engine(self.url, connect_args=args, pool_pre_ping=True, pool_size=1,
                                         max_overflow=1, pool_recycle=300)
        return self._engine

    @contextmanager
    def connect(self):
        for attempt in range(1, self.retries + 1):
            try:
                conn = self.engine.connect()
                break
            except Exception as e:
                if type(e).__name__ not in RETRYABLE or attempt == self.retries:
                    raise
                logger.warning("Postgres not ready (%s), retry %d", type(e).__name__, attempt)
                time.sleep(2 ** attempt)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.connect() as conn, conn.begin():
            yield conn

    def execute(self, sql: str, params: dict | list | None = None) -> int:
        """Run one statement; a list of dicts runs it once per row. Returns rowcount."""
        from sqlalchemy import text

        with self.transaction() as conn:
            return conn.execute(text(sql), params or {}).rowcount

    def fetch(self, sql: str, params: dict | None = None) -> list[dict]:
        from sqlalchemy import text

        with self.connect() as conn:
            return [dict(row._mapping) for row in conn.execute(text(sql), params or {})]

    def read_df(self, sql: str, params: dict | None = None, read_only: bool = False):
        """SELECT into a pandas DataFrame. read_only=True is enforced by Postgres itself."""
        import pandas as pd
        from sqlalchemy import text

        with self.connect() as conn:
            trans = conn.begin()
            try:
                if read_only:
                    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                return pd.read_sql(text(sql), conn, params=params)
            finally:
                trans.rollback()

    def run_script(self, script: str) -> None:
        """Run a multi-statement SQL script (e.g. a migration) in one transaction."""
        with self.transaction() as conn:
            for statement in (s.strip() for s in script.split(";")):
                if statement:
                    conn.exec_driver_sql(statement)

    def migrate(self, directory: str) -> list[str]:
        """Apply NNN_name.sql files from `directory` once each, tracked in public.schema_migrations."""
        from pathlib import Path

        self.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations "
                     "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r["version"] for r in self.fetch("SELECT version FROM public.schema_migrations")}
        applied = []
        for path in sorted(Path(directory).glob("*.sql")):
            if path.stem not in done:
                self.run_script(path.read_text())
                self.execute("INSERT INTO public.schema_migrations (version) VALUES (:v)", {"v": path.stem})
                applied.append(path.name)
        return applied

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
