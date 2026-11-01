# Discord discards an interaction response that arrives after 3s. The bot Lambda
# answers inline, so its Duration IS the user-visible latency budget. Alarm well
# under the deadline so a regression surfaces before users see
# "The application did not respond".
resource "aws_cloudwatch_metric_alarm" "bot_lambda_slow_response" {
  alarm_name        = "${var.app_name}-${var.deployment_env}-slow-interaction-response"
  alarm_description = "Bot Lambda p99 Duration is approaching Discord's 3s interaction deadline."

  namespace          = "AWS/Lambda"
  metric_name        = "Duration"
  extended_statistic = "p99"
  period             = 300
  evaluation_periods = 1

  # Duration EXCLUDES init (cold start). Adomi once hit 1891ms Duration + 1128ms
  # init = 3020ms total, so a threshold near 3000 would stay green through a
  # real timeout. 1500 leaves room for a cold start on top.
  threshold           = 1500
  comparison_operator = "GreaterThanThreshold"
  unit                = "Milliseconds"

  treat_missing_data = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.bot_lambda.function_name
  }

  # No alarm_actions: nothing subscribes yet. Wire an SNS topic here when one exists.
}
