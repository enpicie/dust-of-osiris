# ── Feature: Deferred worker (callbacks) ─────────────────────────────────────
# Commands that can't answer inside Discord's 3s deadline reply with a
# placeholder and enqueue here; the worker Lambda posts the real answer as a
# followup.

locals {
  # MIRROR: .github/workflows/workflow-deploy.yml uploads the worker zip under
  # this name — keep the two in sync.
  deferred_worker_name = "${var.app_name}-deferred-worker"
}

# Messages that fail maxReceiveCount times land here instead of retrying until
# retention expires. The handler already answers the user on errors, so anything
# here means the followup itself (or the Lambda) failed — inspect, then purge.
resource "aws_sqs_queue" "deferred_worker_dlq" {
  name                      = "${local.deferred_worker_name}-dlq-${var.deployment_env}"
  message_retention_seconds = 1209600 # 14 days, the SQS maximum
}

resource "aws_sqs_queue" "deferred_worker" {
  name = "${local.deferred_worker_name}-${var.deployment_env}"

  # Must exceed the deferred_worker Lambda timeout (480s below) so a message is not
  # redelivered while a consumer invocation is still running.
  visibility_timeout_seconds = 540
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.deferred_worker_dlq.arn
    maxReceiveCount     = 3
  })
}

data "aws_s3_object" "deferred_worker_zip_latest" {
  bucket = var.bucket_name
  key    = "${local.deferred_worker_name}/${local.deferred_worker_name}-latest.zip"
}

data "aws_s3_object" "deferred_worker_layer_zip" {
  bucket = var.bucket_name
  key    = var.deferred_worker_lambda_layer_s3_key
}

data "aws_s3_object" "deferred_worker_layer_hash" {
  bucket = var.bucket_name
  key    = var.deferred_worker_lambda_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "deferred_worker_layer" {
  layer_name               = "${local.deferred_worker_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${local.deferred_worker_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.deferred_worker_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.deferred_worker_layer_hash.body)
}

resource "aws_lambda_function" "deferred_worker" {
  function_name = "${local.deferred_worker_name}-${var.deployment_env}"
  s3_bucket     = data.aws_s3_bucket.lambda_bucket.id
  s3_key        = data.aws_s3_object.deferred_worker_zip_latest.key
  handler       = "handler.handler"
  runtime       = "python${var.python_runtime}"
  architectures = [var.architecture]
  role          = aws_iam_role.deferred_worker_role.arn
  # Discord accepts followups for 15 minutes after the interaction; 8 minutes
  # leaves room for queue wait before the work starts.
  timeout     = 480
  memory_size = 512

  layers = [
    aws_lambda_layer_version.deferred_worker_layer.arn
  ]

  environment {
    variables = {
      REGION                        = var.aws_region
      DISCORD_BOT_TOKEN_SECRET_NAME = aws_secretsmanager_secret.discord_bot_token.name
    }
  }

  source_code_hash = data.aws_s3_object.deferred_worker_zip_latest.etag
}

resource "aws_lambda_event_source_mapping" "deferred_worker_trigger" {
  event_source_arn = aws_sqs_queue.deferred_worker.arn
  function_name    = aws_lambda_function.deferred_worker.arn
  batch_size       = 1
}

# ── IAM ──────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "deferred_worker_role" {
  name = "LambdaExecutionRole-${local.deferred_worker_name}-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "deferred_worker_basic_execution" {
  role       = aws_iam_role.deferred_worker_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "deferred_worker_sqs_policy" {
  name = "LambdaSQSPolicy-${local.deferred_worker_name}-${var.deployment_env}"
  role = aws_iam_role.deferred_worker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSConsume"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.deferred_worker.arn
      }
    ]
  })
}

# Bot Lambda may enqueue deferred work.
resource "aws_iam_role_policy" "lambda_deferred_worker_send_policy" {
  name = "LambdaSQSSendPolicy-${var.app_name}-${var.deployment_env}"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "SQSSendDeferredWork",
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:SendMessageBatch"]
        Resource = aws_sqs_queue.deferred_worker.arn
      }
    ]
  })
}
