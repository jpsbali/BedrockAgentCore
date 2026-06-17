variable "name" {
  description = "Name of the API key credential provider"
  type        = string
}

variable "api_key" {
  description = "The API key value to inject"
  type        = string
  sensitive   = true
}
