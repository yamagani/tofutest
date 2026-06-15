variable "region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Base name for all resources"
  type        = string
  default     = "insurance-extractor"
}

variable "image_tag" {
  description = "Container image tag to deploy (set by the deploy script)"
  type        = string
  default     = "latest"
}

variable "architecture" {
  description = "Lambda architecture (arm64 = Graviton, cheaper)"
  type        = string
  default     = "arm64"
}

variable "memory_size" {
  description = "Lambda memory (MB). CPU scales with memory; 2048 gives ~1.2 vCPU."
  type        = number
  default     = 2048
}

variable "timeout" {
  description = "Lambda timeout (seconds). OCR + mapping is well under this."
  type        = number
  default     = 30
}
