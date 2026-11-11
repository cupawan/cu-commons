"""Settings from environment variables, optionally filled from AWS SSM Parameter Store.

Clients in this package never read configuration on their own: pass values explicitly, or use their
``from_env()`` constructors, which read the variable names documented on each client.
In AWS Lambda, call ``load_ssm("/myapp/prod/")`` once per cold start to copy parameters into the
environment (existing environment variables win, which keeps local runs and tests simple).
"""
import logging
import os

from cu_commons.errors import ConfigError

logger = logging.getLogger(__name__)
_loaded_prefixes: set[str] = set()


def get(name: str, default: str | None = None, required: bool = True) -> str | None:
    value = os.environ.get(name, default)
    if required and value in (None, ""):
        raise ConfigError(f"Missing setting: {name}")
    return value


def _ssm_client(region: str | None = None):
    import boto3

    return boto3.client("ssm", region_name=region)


def load_ssm(prefix: str, region: str | None = None, client=None, force: bool = False) -> int:
    """Copy every parameter under `prefix` into os.environ (names relative to the prefix).

    Returns how many variables were set. Cached per prefix for the life of the process.
    """
    prefix = prefix if prefix.endswith("/") else prefix + "/"
    if prefix in _loaded_prefixes and not force:
        return 0
    ssm = client or _ssm_client(region)
    count = 0
    for page in ssm.get_paginator("get_parameters_by_path").paginate(Path=prefix, Recursive=True, WithDecryption=True):
        for param in page["Parameters"]:
            name = param["Name"][len(prefix):].replace("/", "_")
            if name not in os.environ:
                os.environ[name] = param["Value"]
                count += 1
    _loaded_prefixes.add(prefix)
    logger.info("Loaded %d parameters from %s", count, prefix)
    return count


def put_ssm(name: str, value: str, prefix: str, region: str | None = None, client=None) -> None:
    """Store a (rotated) secret as a SecureString and update os.environ."""
    prefix = prefix if prefix.endswith("/") else prefix + "/"
    (client or _ssm_client(region)).put_parameter(Name=prefix + name, Value=value, Type="SecureString", Overwrite=True)
    os.environ[name] = value
