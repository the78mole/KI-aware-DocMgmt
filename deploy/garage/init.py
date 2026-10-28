"""Richtet den Garage-Knoten im Compose-Stack ein: Layout, Bucket, Zugangsschlüssel.

Idempotent, darf bei jedem Start laufen. Nutzt nur die Standardbibliothek und die Admin-API v2.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

ADMIN_URL = os.environ.get("GARAGE_ADMIN_URL", "http://garage:3903")
ADMIN_TOKEN = os.environ["GARAGE_ADMIN_TOKEN"]
BUCKET = os.environ.get("S3_BUCKET", "docmgmt")
KEY_ID = os.environ["S3_ACCESS_KEY_ID"]
KEY_SECRET = os.environ["S3_SECRET_ACCESS_KEY"]
CAPACITY = int(os.environ.get("GARAGE_CAPACITY_BYTES", str(10 * 1024**3)))


def call(endpoint: str, body: dict | None = None, ok_codes: tuple[int, ...] = ()) -> dict:
    request = urllib.request.Request(
        f"{ADMIN_URL}/v2/{endpoint}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in ok_codes:
            return {}
        raise SystemExit(f"{endpoint}: HTTP {exc.code} {exc.read().decode()}") from exc


def wait_for_garage() -> dict:
    for _ in range(60):
        try:
            return call("GetClusterStatus")
        except (urllib.error.URLError, ConnectionError):
            time.sleep(1)
    raise SystemExit("Garage-Admin-API nicht erreichbar")


def main() -> None:
    status = wait_for_garage()
    node = status["nodes"][0]
    if node.get("role") is None:
        layout = call("GetClusterLayout")
        call("UpdateClusterLayout", {"roles": [{"id": node["id"], "zone": "dc1", "capacity": CAPACITY, "tags": []}]})
        call("ApplyClusterLayout", {"version": layout["version"] + 1})
        print(f"Layout angelegt für Knoten {node['id'][:16]}")

    call("CreateBucket", {"globalAlias": BUCKET}, ok_codes=(409,))
    call("ImportKey", {"accessKeyId": KEY_ID, "secretAccessKey": KEY_SECRET, "name": "docmgmt"}, ok_codes=(409,))
    bucket = call(f"GetBucketInfo?globalAlias={BUCKET}")
    call(
        "AllowBucketKey",
        {"bucketId": bucket["id"], "accessKeyId": KEY_ID, "permissions": {"read": True, "write": True, "owner": False}},
    )
    print(f"Bucket {BUCKET!r} bereit")


if __name__ == "__main__":
    sys.exit(main())
