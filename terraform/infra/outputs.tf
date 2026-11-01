output "lambda_function_name" {
  description = "Name of the main bot Lambda function"
  value       = aws_lambda_function.bot_lambda.function_name
}

output "interactions_endpoint_url" {
  description = "Paste into Discord Developer Portal > General Information > Interactions Endpoint URL"
  value       = "${aws_apigatewayv2_stage.env_stage.invoke_url}/${var.app_name}"
}


output "deferred_worker_queue_url" {
  description = "URL of the SQS queue feeding the deferred worker"
  value       = aws_sqs_queue.deferred_worker.url
}

output "deferred_worker_dlq_url" {
  description = "URL of the deferred worker's dead-letter queue"
  value       = aws_sqs_queue.deferred_worker_dlq.url
}
