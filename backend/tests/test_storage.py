import io
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from docmgmt.config import Settings
from docmgmt.storage import ObjectNotFoundError, S3Storage


@pytest.fixture
def s3_storage() -> Iterator[S3Storage]:
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="docmgmt")
        settings = Settings(s3_endpoint_url="https://s3.amazonaws.com", s3_region="us-east-1", s3_access_key_id="x")
        yield S3Storage.from_settings(settings)


def test_put_and_open_roundtrip(s3_storage: S3Storage) -> None:
    s3_storage.put("documents/a/original.pdf", io.BytesIO(b"%PDF"), "application/pdf")

    assert b"".join(s3_storage.open("documents/a/original.pdf")) == b"%PDF"


def test_open_missing_key_raises(s3_storage: S3Storage) -> None:
    with pytest.raises(ObjectNotFoundError):
        s3_storage.open("fehlt")
