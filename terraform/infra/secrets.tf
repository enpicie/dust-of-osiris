# ── Feature: Discord bot token in Secrets Manager ────────────────────────────
# Only needed when the bot calls the Discord REST API with its token (roles,
# channel posts, guild lookups — see src/utils/discord_api_helper.py).
# Interaction replies and deferred followups do NOT need it. The Lambdas get
# the secret's NAME as an env var and fetch the value at runtime; the token is
# never a plaintext env var.

resource "aws_secretsmanager_secret" "discord_bot_token" {
  name        = "${var.app_name}-discord-bot-token-${var.deployment_env}"
  description = "Discord bot token for ${var.app_name}"
}

resource "aws_secretsmanager_secret_version" "discord_bot_token" {
  secret_id     = aws_secretsmanager_secret.discord_bot_token.id
  secret_string = var.discord_bot_token
}

resource "aws_iam_role_policy" "lambda_secrets_policy" {
  name = "LambdaSecretsPolicy-${var.app_name}-${var.deployment_env}"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "GetDiscordBotToken",
        Effect   = "Allow",
        Action   = "secretsmanager:GetSecretValue",
        Resource = aws_secretsmanager_secret.discord_bot_token.arn
      }
    ]
  })
}

# Deferred worker's token access.
resource "aws_iam_role_policy" "deferred_worker_secrets_policy" {
  name = "LambdaSecretsPolicy-${local.deferred_worker_name}-${var.deployment_env}"
  role = aws_iam_role.deferred_worker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "GetDiscordBotToken"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = aws_secretsmanager_secret.discord_bot_token.arn
      }
    ]
  })
}
