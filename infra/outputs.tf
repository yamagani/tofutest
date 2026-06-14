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
