variable "name" {
  description = "Name of the OAuth2 credential provider"
  type        = string
}

variable "client_id" {
  description = "Client ID for the OAuth2 provider"
  type        = string
}

variable "client_secret" {
  description = "Client Secret for the OAuth2 provider"
  type        = string
  sensitive   = true
}

variable "discovery_url" {
  description = "OIDC Discovery URL"
  type        = string
}
