variable "project_id" {
  type = string
}

variable "secret_names" {
  type = list(string)
  default = [
    "ssi-fc-username",
    "ssi-fc-password",
    "telegram-bot-token",
    "telegram-chat-id",
  ]
}
