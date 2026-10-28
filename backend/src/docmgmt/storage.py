from collections.abc import Iterator
from typing import BinaryIO, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import Request

from docmgmt.config import Settings

CHUNK_SIZE = 1024 * 1024


class ObjectNotFoundError(Exception):
    pass


class ObjectStorage(Protocol):
    def put(self, key: str, data: BinaryIO, content_type: str) -> None: ...

    def open(self, key: str) -> Iterator[bytes]:
        """Liefert den Inhalt in Blöcken; wirft ObjectNotFoundError, wenn der Schlüssel fehlt."""
        ...


class S3Storage:
    """Ablage in einem S3-kompatiblen Speicher (Garage im Compose-Stack)."""

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3Storage":
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            # Garage unterstützt keine virtual-hosted Buckets ohne root_domain
            config=Config(s3={"addressing_style": "path"}),
        )
        return cls(client, settings.s3_bucket)

    def put(self, key: str, data: BinaryIO, content_type: str) -> None:
        self._client.upload_fileobj(data, self._bucket, key, ExtraArgs={"ContentType": content_type})

    def open(self, key: str) -> Iterator[bytes]:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise ObjectNotFoundError(key) from exc
            raise
        return response["Body"].iter_chunks(CHUNK_SIZE)


def get_storage(request: Request) -> ObjectStorage:
    return request.app.state.storage
