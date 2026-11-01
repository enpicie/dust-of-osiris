terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.36.0"
    }
  }
  # Configured at init time by enpicie/gh-action-workflow-terraform-run
  # (state_key in .github/workflows/workflow-deploy.yml).
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}
