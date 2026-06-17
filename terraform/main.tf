resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# --- Cognito Module ---

module "cognito" {
  source = "./modules/cognito"

  pool_name                  = "mcp-user-pool-${random_string.suffix.result}"
  domain_prefix              = "mcp-gateway-${random_string.suffix.result}"
  resource_server_identifier = "kyc-mcp"
  client_name                = "mcp-client"
}

# --- OAuth2 Credential Provider ---

module "oauth2_credential_provider" {
  source = "./modules/oauth2_credential_provider"

  name          = "cognito-oauth-provider-${random_string.suffix.result}"
  client_id     = module.cognito.client_id
  client_secret = module.cognito.client_secret
  discovery_url = module.cognito.discovery_url
}

# --- S3 Bucket ---

resource "aws_s3_bucket" "support_tools_artifacts" {
  bucket_prefix = "kyc-artifacts-"
  force_destroy = true
}

# --- Build Docker Images ---

module "docker_build_kyc_agent" {
  source          = "./modules/docker_build_push"
  repo_name       = "kyc-agent-${random_string.suffix.result}"
  source_path     = "../agent_code/kyc_agent"
  dockerfile_path = "Dockerfile"
  target_arch     = "ARM64"
}

module "docker_build_kyc_tools" {
  source          = "./modules/docker_build_push"
  repo_name       = "kyc-agent-mcp-${random_string.suffix.result}"
  source_path     = "../agent_code/kyc_tools"
  dockerfile_path = "Dockerfile"
  target_arch     = "ARM64"
}

module "docker_build_doc_extraction_agent" {
  source          = "./modules/docker_build_push"
  repo_name       = "doc-extraction-agent-${random_string.suffix.result}"
  source_path     = "../agent_code/doc_extraction_agent"
  dockerfile_path = "Dockerfile"
  target_arch     = "ARM64"
}

module "docker_build_property_research_agent" {
  source          = "./modules/docker_build_push"
  repo_name       = "property-research-agent-${random_string.suffix.result}"
  source_path     = "../agent_code/property_research_agent"
  dockerfile_path = "Dockerfile"
  target_arch     = "ARM64"
}

module "docker_build_consolidation_agent" {
  source          = "./modules/docker_build_push"
  repo_name       = "consolidation-agent-${random_string.suffix.result}"
  source_path     = "../agent_code/consolidation_agent"
  dockerfile_path = "Dockerfile"
  target_arch     = "ARM64"
}

# --- AgentCore Runtimes ---

module "runtime_kyc_tools" {
  source                      = "./modules/agentcore_runtime"
  agent_runtime_name          = "kyc_tools_${random_string.suffix.result}"
  agent_runtime_container_uri = module.docker_build_kyc_tools.ecr_uri
  server_protocol             = "MCP"
  cognito_discovery_url       = module.cognito.discovery_url
  allowed_clients             = [module.cognito.client_id]
  environment_variables = {
    LOG_LEVEL = "INFO"
    ENV       = "production"
  }
  request_header_allowlist = ["X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId"]
  depends_on               = [module.docker_build_kyc_tools]
}

module "runtime_kyc_agent" {
  source                      = "./modules/agentcore_runtime"
  agent_runtime_name          = "kyc_agent_${random_string.suffix.result}"
  agent_runtime_container_uri = module.docker_build_kyc_agent.ecr_uri
  server_protocol             = "HTTP"
  environment_variables = {
    LOG_LEVEL          = "INFO"
    ENV                = "production"
    OAUTH2_ID_PROVIDER = module.oauth2_credential_provider.credential_provider_name
    MCP_URL            = local.kyc_tools_url
    MEMORY_ID          = module.memory.memory_id
  }
  request_header_allowlist = ["X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId"]
  depends_on               = [module.docker_build_kyc_agent]
}

module "runtime_doc_extraction_agent" {
  source                      = "./modules/agentcore_runtime"
  agent_runtime_name          = "doc_extraction_agent_${random_string.suffix.result}"
  agent_runtime_container_uri = module.docker_build_doc_extraction_agent.ecr_uri
  server_protocol             = "HTTP"
  environment_variables = {
    LOG_LEVEL = "INFO"
    ENV       = "production"
    MEMORY_ID = module.memory.memory_id
  }
  request_header_allowlist = ["X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId"]
  depends_on               = [module.docker_build_doc_extraction_agent]
}

module "runtime_property_research_agent" {
  source                      = "./modules/agentcore_runtime"
  agent_runtime_name          = "property_research_agent_${random_string.suffix.result}"
  agent_runtime_container_uri = module.docker_build_property_research_agent.ecr_uri
  server_protocol             = "HTTP"
  environment_variables = {
    LOG_LEVEL      = "INFO"
    ENV            = "production"
    S3_BUCKET_NAME = aws_s3_bucket.support_tools_artifacts.id
    MEMORY_ID      = module.memory.memory_id
  }
  request_header_allowlist = ["X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId"]
  depends_on               = [module.docker_build_property_research_agent]
}

module "runtime_consolidation_agent" {
  source                      = "./modules/agentcore_runtime"
  agent_runtime_name          = "consolidation_agent_${random_string.suffix.result}"
  agent_runtime_container_uri = module.docker_build_consolidation_agent.ecr_uri
  server_protocol             = "HTTP"
  environment_variables = {
    LOG_LEVEL             = "INFO"
    ENV                   = "production"
    MEMORY_ID             = module.memory.memory_id
    GEOCODING_GATEWAY_URL = module.geocoding_gateway.gateway_url
    OAUTH2_ID_PROVIDER    = module.oauth2_credential_provider.credential_provider_name
  }
  request_header_allowlist = ["X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId"]
  depends_on               = [module.docker_build_consolidation_agent]
}

# --- Additional IAM Policies ---

resource "aws_iam_role_policy" "property_research_s3_access" {
  name = "property-research-s3-access"
  role = module.runtime_property_research_agent.agent_runtime_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          "${aws_s3_bucket.support_tools_artifacts.arn}",
          "${aws_s3_bucket.support_tools_artifacts.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "property_research_agentcore_tools" {
  name = "property-research-agentcore-tools"
  role = module.runtime_property_research_agent.agent_runtime_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateCodeInterpreter",
          "bedrock-agentcore:StartCodeInterpreterSession",
          "bedrock-agentcore:InvokeCodeInterpreter",
          "bedrock-agentcore:StopCodeInterpreterSession",
          "bedrock-agentcore:DeleteCodeInterpreter",
          "bedrock-agentcore:ListCodeInterpreters",
          "bedrock-agentcore:GetCodeInterpreter",
          "bedrock-agentcore:CreateBrowser",
          "bedrock-agentcore:DeleteBrowser",
          "bedrock-agentcore:ListBrowsers",
          "bedrock-agentcore:StartBrowserSession",
          "bedrock-agentcore:GetBrowserSession",
          "bedrock-agentcore:GetBrowser",
          "bedrock-agentcore:ConnectBrowserAutomationStream",
          "bedrock-agentcore:ConnectBrowserLiveViewStream",
          "bedrock-agentcore:UpdateBrowserStream",
          "bedrock-agentcore:ListBrowserSessions",
          "bedrock-agentcore:StopBrowserSession"
        ]
        Resource = "*"
      }
    ]
  })
}

# --- Locals ---

locals {
  runtime_url_base = "https://bedrock-agentcore.${data.aws_region.current.region}.amazonaws.com/runtimes"

  kyc_tools_arn_encoded = replace(replace(module.runtime_kyc_tools.agent_runtime_arn, ":", "%3A"), "/", "%2F")
  kyc_tools_url         = "${local.runtime_url_base}/${local.kyc_tools_arn_encoded}/invocations/?qualifier=DEFAULT"
}

# --- Geocoding Gateway (OpenAPI → MCP) ---

resource "aws_s3_object" "openstreetmap_schema" {
  bucket = aws_s3_bucket.support_tools_artifacts.id
  key    = "api_schemas/openstreetmap.json"
  source = "${path.module}/../sample_data/api_schemas/openstreetmap.json"
  etag   = filemd5("${path.module}/../sample_data/api_schemas/openstreetmap.json")
}

module "nominatim_api_key" {
  source  = "./modules/api_key_credential_provider"
  name    = "nominatim-useragent-${random_string.suffix.result}"
  api_key = "KYC-Workshop/1.0 (mortgage-application-research)"
}

module "geocoding_gateway" {
  source = "./modules/agentcore_gateway"

  name                      = "geocoding-gateway-${random_string.suffix.result}"
  description               = "Nominatim geocoding API exposed as MCP tools"
  instructions              = "Use the searchAddress tool to geocode addresses and get lat/lon coordinates."
  cognito_discovery_url     = module.cognito.discovery_url
  allowed_clients           = [module.cognito.client_id]
  target_name               = "nominatim-geocoding"
  target_description        = "OpenStreetMap Nominatim address search"
  credential_provider_arn   = module.nominatim_api_key.arn
  credential_location       = "HEADER"
  credential_parameter_name = "User-Agent"
  openapi_schema_s3_uri     = "s3://${aws_s3_bucket.support_tools_artifacts.id}/${aws_s3_object.openstreetmap_schema.key}"

  depends_on = [aws_s3_object.openstreetmap_schema]
}

# --- Secrets Manager ---

resource "aws_secretsmanager_secret" "client_creds" {
  name = "mcp-client-creds-${random_string.suffix.result}"
}

resource "aws_secretsmanager_secret_version" "client_creds" {
  secret_id = aws_secretsmanager_secret.client_creds.id
  secret_string = jsonencode({
    client_id     = module.cognito.client_id
    client_secret = module.cognito.client_secret
    issuer_url    = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${module.cognito.user_pool_id}"
    token_url     = module.cognito.token_endpoint
    scope         = "kyc-mcp/access"
  })
}

# --- AgentCore Memory ---

module "memory" {
  source = "./modules/memory"
  name   = "kyc_workshop_memory"
  suffix = random_string.suffix.result
}

# --- AgentCore Observability (CloudWatch Logs + X-Ray) ---

module "observability_memory" {
  source       = "./modules/observability"
  resource_id  = "memory"
  resource_arn = module.memory.memory_arn
}

module "observability_geocoding_gateway" {
  source       = "./modules/observability"
  resource_id  = "geocoding-gateway"
  resource_arn = module.geocoding_gateway.gateway_arn
  depends_on   = [module.geocoding_gateway]
}

module "observability_code_interpreter" {
  source       = "./modules/observability"
  resource_id  = "code-interpreter"
  resource_arn = "arn:aws:bedrock-agentcore:${data.aws_region.current.region}:aws:code-interpreter/aws.codeinterpreter.v1"
}

module "observability_browser" {
  source          = "./modules/observability"
  resource_id     = "browser"
  resource_arn    = "arn:aws:bedrock-agentcore:${data.aws_region.current.region}:aws:browser/aws.browser.v1"
  enable_app_logs = false
}
