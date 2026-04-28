"""Format alert payloads into Telegram Markdown messages.

Adds severity emoji + bold title + body + Cloud Logging deep-link footer.
"""

from urllib.parse import quote_plus

SEVERITY_EMOJI = {
    "critical": "[CRIT]",
    "error": "[ERR]",
    "warning": "[WARN]",
    "info": "[INFO]",
    "debug": "[DBG]",
}


def format_alert(
    severity: str,
    name: str,
    body: str,
    project_id: str | None = None,
    source: str | None = None,
    extra: dict | None = None,
) -> str:
    """Return a Telegram Markdown-formatted message string.

    Format:
      `[CRIT] *<name>*`
      `<body>`
      `\nsource: <source>` (if given)
      `key1: val1` (extra fields)
      `[Logs](https://...)` (if project_id)
    """
    tag = SEVERITY_EMOJI.get(severity, f"[{severity.upper()}]")
    lines = [f"{tag} *{_escape(name)}*", _escape(body)]
    if source:
        lines.append(f"source: `{_escape(source)}`")
    if extra:
        for k, v in extra.items():
            lines.append(f"{_escape(str(k))}: `{_escape(str(v))}`")
    if project_id:
        log_url = _logs_url(project_id, name)
        lines.append(f"[Logs]({log_url})")
    return "\n".join(lines)


def _logs_url(project_id: str, alert_name: str) -> str:
    query = f'labels."alert_name"="{alert_name}"'
    return (
        f"https://console.cloud.google.com/logs/query;"
        f"query={quote_plus(query)}?project={project_id}"
    )


def _escape(s: str) -> str:
    """Escape Telegram Markdown reserved chars."""
    return s.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
