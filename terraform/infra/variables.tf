# config.env settings passed in as ENV variables from GitHub Actions workflow
variable "app_name" {
  description = "The name of the application"
  type        = string
}

variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
}

variable "python_runtime" {
  description = "Python runtime for Lambda (e.g., 3.12)"
  type        = string
}

variable "architecture" {
  description = "Architecture for Lambda (e.g., x86_64, arm64)"
  type        = string
}

variable "deployment_env" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket to store Lambda artifacts"
  type        = string
}

variable "app_lambda_layer_s3_key" {
  description = "S3 key for .zip of Lambda layer built for this application"
  type        = string
}

variable "app_lambda_layer_hash_s3_key" {
  description = "S3 key for .hash file for Lambda layer built for this application"
  type        = string
}

variable "deferred_worker_lambda_layer_s3_key" {
  description = "S3 key for .zip of Lambda layer built for the deferred worker"
  type        = string
}

variable "deferred_worker_lambda_layer_hash_s3_key" {
  description = "S3 key for .hash file for Lambda layer built for the deferred worker"
  type        = string
}

variable "discord_public_key" {
  description = "Public Key for Discord bot verification"
  type        = string
}

variable "discord_bot_token" {
  description = "Discord bot token — stored in Secrets Manager, fetched by Lambdas at runtime"
  type        = string
  sensitive   = true
}
