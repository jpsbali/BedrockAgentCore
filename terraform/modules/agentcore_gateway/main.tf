data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_role" "gateway_role" {
  name = "${var.name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "gateway_permissions" {
  name = "${var.name}-permissions"
  role = aws_iam_role.gateway_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["iam:PassRole", "iam:GetRole"]
      Resource = aws_iam_role.gateway_role.arn
    }]
  })
}

resource "aws_bedrockagentcore_gateway" "this" {
  name        = var.name
  description = var.description
  role_arn    = aws_iam_role.gateway_role.arn

  authorizer_type = "CUSTOM_JWT"
  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = var.cognito_discovery_url
      allowed_clients  = var.allowed_clients
    }
  }

  protocol_type = "MCP"
  protocol_configuration {
    mcp {
      instructions       = var.instructions
      search_type        = "SEMANTIC"
      supported_versions = ["2025-03-26", "2025-06-18"]
    }
  }
}

resource "aws_bedrockagentcore_gateway_target" "this" {
  name               = var.target_name
  gateway_identifier = aws_bedrockagentcore_gateway.this.gateway_id
  description        = var.target_description

  credential_provider_configuration {
    api_key {
      provider_arn              = var.credential_provider_arn
      credential_location      = var.credential_location
      credential_parameter_name = var.credential_parameter_name
    }
  }

  target_configuration {
    mcp {
      open_api_schema {
        s3 {
          uri = var.openapi_schema_s3_uri
        }
      }
    }
  }
}
