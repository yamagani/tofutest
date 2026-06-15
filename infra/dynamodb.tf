# Job records for the async extraction API. On-demand billing (no capacity to
# manage). The app reads the table name from IE_DDB_TABLE.
resource "aws_dynamodb_table" "jobs" {
  name         = "${var.name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}
