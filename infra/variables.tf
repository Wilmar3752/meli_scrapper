variable "project_name" {
  description = "Name for the Lambda function and ECR repository"
  type        = string
  default     = "meli-scrapper"
}

variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "memory_size" {
  description = "Lambda memory in MB (Chromium needs >= 2048)"
  type        = number
  default     = 2048
}

variable "timeout" {
  description = "Lambda timeout in seconds (max 900)"
  type        = number
  default     = 900
}
