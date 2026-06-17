variable "name" {
  description = "Name of the gateway"
  type        = string
}

variable "description" {
  description = "Description of the gateway"
  type        = string
  default     = ""
}

variable "instructions" {
  description = "Instructions for the MCP gateway"
  type        = string
  default     = ""
}

variable "cognito_discovery_url" {
  description = "Cognito OpenID discovery URL for JWT authorization"
  type        = string
}

variable "allowed_clients" {
  description = "List of allowed Cognito client IDs"
  type        = list(string)
}

variable "allowed_audience" {
  description = "List of allowed audiences for JWT validation"
  type        = list(string)
  default     = []
}

variable "target_name" {
  description = "Name of the gateway target"
  type        = string
}

variable "target_description" {
  description = "Description of the gateway target"
  type        = string
  default     = ""
}

variable "credential_provider_arn" {
  description = "ARN of the credential provider for outbound authentication"
  type        = string
}

variable "credential_location" {
  description = "Where to place the credential (HEADER, QUERY)"
  type        = string
  default     = "HEADER"
}

variable "credential_parameter_name" {
  description = "Name of the header or query parameter for the credential"
  type        = string
}

variable "openapi_schema_s3_uri" {
  description = "S3 URI of the OpenAPI schema JSON file"
  type        = string
}
