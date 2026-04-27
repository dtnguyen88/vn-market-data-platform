# Secrets

This directory documents secret **resource definitions** only. Real values are
populated out-of-band by the operator and **never** committed.

## Populating secrets

```bash
# Generate next version of a secret
echo -n "your-actual-ssi-username" | gcloud secrets versions add ssi-fc-username --data-file=-

# Verify
gcloud secrets versions access latest --secret=ssi-fc-username
```

## Inventory

| Secret | Phase populated | Used by |
|---|---|---|
| `ssi-fc-username` | Phase 03 | realtime-publisher |
| `ssi-fc-password` | Phase 03 | realtime-publisher |
| `telegram-bot-token` | Phase 07 | telegram-alerter |
| `telegram-chat-id` | Phase 07 | telegram-alerter |

## Rotation

- Telegram tokens: regenerate via @BotFather, add new version, services pick up next deploy.
- SSI FC: contact SSI to rotate; same procedure.
