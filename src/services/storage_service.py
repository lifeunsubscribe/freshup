import boto3
from botocore.config import Config
from src.config import get_settings


def get_storage_client():
    """Get an S3-compatible storage client.

    Points to MinIO locally, swap to real S3 via environment config.
    """
    settings = get_settings()

    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )
