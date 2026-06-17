variable "agent_runtime_name" {
  description = "Name of the Agent Runtime"
  type        = string
}

variable "cognito_discovery_url" {
  description = "Cognito OpenID discovery URL"
  type        = string
  default     = null
}

variable "allowed_clients" {
  description = "List of allowed Cognito client IDs"
  type        = list(string)
  default     = null
}

variable "artifact_bucket_id" {
  description = "ID of the S3 bucket containing the runtime code artifact"
  type        = string
  default     = null
}

variable "artifact_object_key" {
  description = "Key of the runtime code artifact object in S3"
  type        = string
  default     = null
}

variable "agent_runtime_container_uri" {
  description = "URI of the container image for the agent runtime"
  type        = string
  default     = null
}

variable "environment_variables" {
  description = "Map of environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "server_protocol" {
  description = "Protocol for the agent runtime server (e.g., HTTP, MCP)"
  type        = string
  default     = "HTTP"
}

variable "request_header_allowlist" {
  description = "List of HTTP request headers that are allowed to be passed through to the runtime."
  type        = list(string)
  default     = null
}

