# Execution role for the bot Lambda. Each optional feature grants its own
# permissions to this role in its own file, so each feature's grants live
# next to its resources.
resource "aws_iam_role" "lambda_exec_role" {
  name = "LambdaExecutionRole-${var.app_name}-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow",
        Sid    = ""
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
