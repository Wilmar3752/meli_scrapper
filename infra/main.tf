terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

# ── ECR ────────────────────────────────────────────────────────
resource "aws_ecr_repository" "this" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ── IAM Role ───────────────────────────────────────────────────
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ── Lambda Function ────────────────────────────────────────────
# First deploy requires a manual image push or a CI/CD run.
# After that, GitHub Actions updates the image on every push to master.
resource "aws_lambda_function" "this" {
  function_name = var.project_name
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.this.repository_url}:latest"
  role          = aws_iam_role.lambda.arn
  memory_size   = var.memory_size
  timeout       = var.timeout

  depends_on = [aws_iam_role_policy_attachment.lambda_basic]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# ── CloudWatch Logs ────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = 7
}

# ── Function URL ───────────────────────────────────────────────
resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "function_url_public" {
  function_name          = aws_lambda_function.this.function_name
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  principal              = "*"
  function_url_auth_type = "NONE"
}

# Required since October 2025 for Function URLs to work
resource "aws_lambda_permission" "function_url_invoke" {
  function_name = aws_lambda_function.this.function_name
  statement_id  = "FunctionURLAllowPublicInvoke"
  action        = "lambda:InvokeFunction"
  principal     = "*"
}
