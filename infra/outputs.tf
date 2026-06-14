output "api_base_url" {
  description = "Base URL of the deployed REST API"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "extract_json_url" {
  description = "POST a JSON body {filename, content_base64, schema, options} here"
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/extract-json"
}

output "ecr_repository_url" {
  description = "ECR repo to push the container image to"
  value       = aws_ecr_repository.app.repository_url
}

output "function_name" {
  value = aws_lambda_function.app.function_name
}

output "jobs_table_name" {
  description = "DynamoDB table for async job records (set as IE_DDB_TABLE)"
  value       = aws_dynamodb_table.jobs.name
}

output "documents_bucket_name" {
  description = "S3 bucket for uploaded documents (set as IE_S3_BUCKET)"
  value       = aws_s3_bucket.documents.bucket
}
