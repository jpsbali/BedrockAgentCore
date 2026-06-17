variable "resource_id" {
  description = "Short identifier used in naming delivery resources (e.g. 'memory', 'geocoding-gateway')"
  type        = string
}

variable "resource_arn" {
  description = "ARN of the AgentCore resource to observe"
  type        = string
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "enable_app_logs" {
  description = "Whether to enable APPLICATION_LOGS delivery (browser does not support this log type)"
  type        = bool
  default     = true
}
