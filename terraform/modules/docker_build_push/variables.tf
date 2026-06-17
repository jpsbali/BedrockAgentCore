variable "source_path" {
  description = "Path to the directory containing the Dockerfile and source code"
  type        = string
}

variable "repo_name" {
  description = "Name of the ECR repository"
  type        = string
}

variable "target_arch" {
  description = "Target architecture for the Docker image (e.g., ARM64, AMD64)"
  type        = string
  default     = "ARM64"
}

variable "image_tag" {
  description = "Tag for the Docker image"
  type        = string
  default     = "latest"
}

variable "force_delete" {
  description = "Whether to force delete the repository. If true, the repository will be deleted even if it contains images."
  type        = bool
  default     = true
}

variable "dockerfile_path" {
  description = "Path to the Dockerfile relative to source_path"
  type        = string
  default     = "Dockerfile"
}
