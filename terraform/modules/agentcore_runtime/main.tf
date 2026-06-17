data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "aws_iam_role" "agent_runtime_role" {
  name = "${var.agent_runtime_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "agent_runtime_permissions" {
  name = "${var.agent_runtime_name}-permissions"
  role = aws_iam_role.agent_runtime_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRImageAccess"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = [
          "arn:aws:ecr:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:repository/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogStreams",
          "logs:CreateLogGroup"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
        ]
      },
      {
        Sid    = "ECRTokenAccess"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Resource = "*"
        Action   = "cloudwatch:PutMetricData"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "bedrock-agentcore"
          }
        }
      },
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:secret:*"
        ]
      },
      {
        Sid    = "GetAgentAccessToken"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
          "bedrock-agentcore:CreateWorkloadIdentity",
          "bedrock-agentcore:GetResourceOauth2Token"
        ]
        Resource = [
          "*"
        ]
      },
      {
        Sid    = "BedrockModelInvocation"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:*"
        ]
      },
      {
        Sid    = "MemoryAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:ListEvents",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:DeleteEvent",
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:ListMemoryRecords",
          "bedrock-agentcore:BatchCreateMemoryRecords",
          "bedrock-agentcore:BatchDeleteMemoryRecords",
          "bedrock-agentcore:BatchUpdateMemoryRecords",
          "bedrock-agentcore:CreateMemorySession",
          "bedrock-agentcore:ListMemorySessions",
          "bedrock-agentcore:GetMemorySession",
          "bedrock-agentcore:RetrieveMemoryRecords"
        ]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = var.agent_runtime_name
  role_arn           = aws_iam_role.agent_runtime_role.arn

  agent_runtime_artifact {
    dynamic "code_configuration" {
      for_each = var.agent_runtime_container_uri == null ? [1] : []
      content {
        entry_point = ["main.py"]
        runtime     = "PYTHON_3_12"
        code {
          s3 {
            bucket = var.artifact_bucket_id
            prefix = var.artifact_object_key
          }
        }
      }
    }

    dynamic "container_configuration" {
      for_each = var.agent_runtime_container_uri != null ? [1] : []
      content {
        container_uri = var.agent_runtime_container_uri
      }
    }
  }

  environment_variables = var.environment_variables

  dynamic "authorizer_configuration" {
    for_each = var.cognito_discovery_url != null ? [1] : []
    content {
      custom_jwt_authorizer {
        discovery_url   = var.cognito_discovery_url
        allowed_clients = var.allowed_clients
      }
    }
  }

  dynamic "request_header_configuration" {
    for_each = var.request_header_allowlist != null ? [1] : []
    content {
      request_header_allowlist = var.request_header_allowlist
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = var.server_protocol
  }
}
