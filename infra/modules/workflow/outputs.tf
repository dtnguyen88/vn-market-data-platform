output "id" {
  value       = google_workflows_workflow.wf.id
  description = "Fully-qualified workflow resource ID."
}

output "name" {
  value       = google_workflows_workflow.wf.name
  description = "Workflow name."
}
