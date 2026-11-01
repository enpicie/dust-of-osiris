data "aws_s3_bucket" "lambda_bucket" {
  bucket = var.bucket_name
}

data "aws_s3_object" "lambda_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.app_name}/${var.app_name}-latest.zip"
}

# Layer with the bot's dependencies (requirements.txt), including PyNaCl for
# the Discord signature check.
data "aws_s3_object" "app_layer_zip" {
  bucket = var.bucket_name
  key    = var.app_lambda_layer_s3_key
}

data "aws_s3_object" "app_layer_hash" {
  bucket = var.bucket_name
  key    = var.app_lambda_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "app_layer" {
  layer_name               = "${var.app_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.app_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.app_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.app_layer_hash.body)
}

resource "aws_lambda_function" "bot_lambda" {
  function_name = "${var.app_name}-${var.deployment_env}"
  s3_bucket     = data.aws_s3_bucket.lambda_bucket.id
  s3_key        = data.aws_s3_object.lambda_zip_latest.key
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python${var.python_runtime}"
  architectures = [var.architecture]
  # Discord discards an interaction response that arrives later than 3s. Lambda
  # scales CPU with memory, so this is sized for headroom on init + handler time,
  # not for RSS. Do not lower without re-checking p99 Duration (see monitoring.tf).
  memory_size = 1024
  role        = aws_iam_role.lambda_exec_role.arn
  timeout     = 10
  layers = [
    aws_lambda_layer_version.app_layer.arn
  ]
  environment {
    variables = {
      REGION                        = var.aws_region
      PUBLIC_KEY                    = var.discord_public_key
      DISCORD_BOT_TOKEN_SECRET_NAME = aws_secretsmanager_secret.discord_bot_token.name
      DEFERRED_WORKER_QUEUE_URL     = aws_sqs_queue.deferred_worker.url
    }
  }

  # Ensures Lambda updates only if the zip file changes
  source_code_hash = data.aws_s3_object.lambda_zip_latest.etag
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${var.app_name}-${var.deployment_env}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.bot_lambda.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /${var.app_name}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "env_stage" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = var.deployment_env
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bot_lambda.function_name
  principal     = "apigateway.amazonaws.com"

  # fully-qualified source ARN
  source_arn = "${aws_apigatewayv2_api.api.execution_arn}/${var.deployment_env}/POST/${var.app_name}"
}
