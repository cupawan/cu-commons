"""Small S3 helpers (boto3 is preinstalled in AWS Lambda; elsewhere install cu-commons[aws])."""
import json


def _client(client=None, region: str | None = None):
    if client is not None:
        return client
    import boto3

    return boto3.client("s3", region_name=region)


def put_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream", client=None) -> None:
    _client(client).put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def get_bytes(bucket: str, key: str, client=None) -> bytes | None:
    """Object bytes, or None if the key doesn't exist."""
    s3 = _client(client)
    try:
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return None


def put_json(bucket: str, key: str, obj, client=None) -> None:
    put_bytes(bucket, key, json.dumps(obj, default=str).encode(), "application/json", client)


def get_json(bucket: str, key: str, default=None, client=None):
    data = get_bytes(bucket, key, client)
    return default if data is None else json.loads(data)


def share_link(bucket: str, key: str, expires_seconds: int = 3600, client=None) -> str:
    """Temporary download URL (presigned GET)."""
    return _client(client).generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key},
                                                  ExpiresIn=expires_seconds)
