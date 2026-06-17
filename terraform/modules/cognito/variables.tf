variable "pool_name" {
  description = "Name of the User Pool"
  type        = string
}

variable "domain_prefix" {
  description = "Domain prefix for the User Pool"
  type        = string
}

variable "resource_server_identifier" {
  description = "Identifier for the Resource Server"
  type        = string
}

variable "client_name" {
  description = "Name of the User Pool Client"
  type        = string
}
