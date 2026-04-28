# Alerting Operations Guide

## Severity meanings

| Severity | TTL (dedup) | Telegram tag | When to use |
|---|---|---|---|
| critical | 0 (never dedup) | [CRIT] | Service down, data loss |
| error | 10 min | [ERR] | Job failure, fixable |
| warning | 10 min | [WARN] | Coverage drop, latency spike |
| info | 60 min | [INFO] | EOD success, monthly report |
| debug | 5 min | [DBG] | Investigation only |

## Routing

```
Cloud Monitoring alert policy ──┐
Workflow step (publish_alert)   ├─▶ Pub/Sub: platform-alerts ─▶ Cloud Run: telegram-alerter ─▶ Your Telegram
Cloud Billing budget alert      ┘
```

## Telegram bot setup

1. @BotFather → /newbot → capture token
2. Send any message to bot → fetch chat_id from `https://api.telegram.org/bot{token}/getUpdates`
3. `gcloud secrets versions add telegram-bot-token --data-file=- <<< "YOUR_TOKEN"`
4. `gcloud secrets versions add telegram-chat-id --data-file=- <<< "YOUR_CHAT_ID"`
5. Redeploy alerter: `gcloud run services update telegram-alerter --region=asia-southeast1`

## Test alert

```bash
gcloud pubsub topics publish platform-alerts \
  --message='{"severity":"info","name":"test_alert","body":"hello from cli"}' \
  --attribute=severity=info,alert_name=test_alert
```

## Common issues

- **No Telegram message arriving:** check alerter logs (`gcloud run services logs read telegram-alerter`); verify push subscription endpoint URL matches alerter URL.
- **Rate limited:** alerter caps at 30 msg/min; bursts will queue.
- **Dedup window swallowing alerts:** check `alert_dedupe` Firestore collection; manually delete doc to force resend.
