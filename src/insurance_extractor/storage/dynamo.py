"""DynamoDB + S3 JobStore.

Job records live in a DynamoDB table; original documents live in S3. The same
code targets LocalStack (when IE_AWS_ENDPOINT_URL is set) and real AWS otherwise
— only the endpoint/credentials differ.

Complex values (schema, result) are stored as JSON strings to sidestep
DynamoDB's number/Decimal handling and the 400 KB item limit concerns for the
document itself (which lives in S3).
"""

from __future__ import annotations

import json
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import Settings
from ..errors import StorageError
from ..observability import get_logger
from .base import Job, JobStatus, JobStore

log = get_logger(__name__)


class DynamoStore(JobStore):
    def __init__(self, settings: Settings):
        self._s = settings
        # LocalStack accepts any credentials; real AWS uses the role/credential chain.
        creds = {}
        if settings.use_localstack:
            creds = {"aws_access_key_id": "test", "aws_secret_access_key": "test"}
        common = dict(
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
            **creds,
        )
        self._ddb = boto3.client("dynamodb", **common)
        self._s3 = boto3.client("s3", **common)
        self._table = settings.ddb_table
        self._bucket = settings.s3_bucket

    # --- resource bootstrap (local convenience; prod creates via IaC) ---
    def ensure(self) -> None:
        if not self._s.auto_create_resources:
            return
        self._ensure_table()
        self._ensure_bucket()

    def _ensure_table(self) -> None:
        try:
            self._ddb.describe_table(TableName=self._table)
            return
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise StorageError(f"DynamoDB describe failed: {exc}") from exc
        log.info("creating dynamodb table", extra={"extra": {"table": self._table}})
        self._ddb.create_table(
            TableName=self._table,
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        self._ddb.get_waiter("table_exists").wait(TableName=self._table)

    def _ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
            return
        except ClientError:
            pass
        log.info("creating s3 bucket", extra={"extra": {"bucket": self._bucket}})
        kwargs: dict[str, Any] = {"Bucket": self._bucket}
        # us-east-1 must NOT pass a LocationConstraint; every other region must.
        if self._s.aws_region != "us-east-1" and not self._s.use_localstack:
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self._s.aws_region}
        self._s3.create_bucket(**kwargs)

    # --- documents (S3) ---
    def put_document(self, job_id: str, data: bytes) -> str:
        key = f"documents/{job_id}"
        try:
            self._s3.put_object(Bucket=self._bucket, Key=key, Body=data)
        except ClientError as exc:
            raise StorageError(f"S3 put failed: {exc}") from exc
        return key

    def get_document(self, key: str) -> bytes:
        try:
            return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as exc:
            raise StorageError(f"S3 get failed: {exc}") from exc

    # --- jobs (DynamoDB) ---
    def create_job(self, job: Job) -> None:
        try:
            self._ddb.put_item(TableName=self._table, Item=_to_item(job))
        except ClientError as exc:
            raise StorageError(f"DynamoDB put failed: {exc}") from exc

    def update_job(self, job_id: str, **fields: Any) -> None:
        job = self.get_job(job_id)
        if job is None:
            from ..errors import JobNotFoundError

            raise JobNotFoundError(f"Job {job_id} not found")
        for k, v in fields.items():
            setattr(job, k, v)
        self.create_job(job)  # full put; worker is the only writer per job

    def get_job(self, job_id: str) -> Optional[Job]:
        try:
            resp = self._ddb.get_item(TableName=self._table, Key={"job_id": {"S": job_id}})
        except ClientError as exc:
            raise StorageError(f"DynamoDB get failed: {exc}") from exc
        item = resp.get("Item")
        return _from_item(item) if item else None


def _to_item(job: Job) -> dict[str, Any]:
    item = {
        "job_id": {"S": job.job_id},
        "status": {"S": job.status.value},
        "filename": {"S": job.filename},
        "strategy": {"S": job.strategy},
        "created_at": {"S": job.created_at},
        "updated_at": {"S": job.updated_at},
        "schema_json": {"S": json.dumps(job.schema)},
    }
    if job.document_key is not None:
        item["document_key"] = {"S": job.document_key}
    if job.result is not None:
        item["result_json"] = {"S": json.dumps(job.result)}
    if job.error is not None:
        item["error"] = {"S": job.error}
    return item


def _from_item(item: dict[str, Any]) -> Job:
    def s(name: str) -> Optional[str]:
        return item[name]["S"] if name in item else None

    return Job(
        job_id=s("job_id"),
        status=JobStatus(s("status")),
        filename=s("filename") or "",
        strategy=s("strategy") or "rule",
        created_at=s("created_at") or "",
        updated_at=s("updated_at") or "",
        schema=json.loads(s("schema_json") or "{}"),
        document_key=s("document_key"),
        result=json.loads(item["result_json"]["S"]) if "result_json" in item else None,
        error=s("error"),
    )
