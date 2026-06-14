resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "app" {
  function_name = var.name
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  architectures = [var.architecture]
  memory_size   = var.memory_size
  timeout       = var.timeout

  # App config is env-driven (see insurance_extractor.config.Settings).
  environment {
    variables = {
      IE_DEFAULT_STRATEGY = "rule"
      IE_LOG_LEVEL        = "INFO"
      IE_JSON_LOGS        = "true"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.basic,
    aws_cloudwatch_log_group.lambda,
  ]
}
