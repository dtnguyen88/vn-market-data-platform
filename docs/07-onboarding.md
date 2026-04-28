# Onboarding

Goal: fresh laptop → "I can read VN30 daily" in <30 min.

## 1. Prereqs

- macOS / Linux / WSL2
- Python 3.12 (`brew install python@3.12` or apt)
- `gcloud` CLI ([install](https://cloud.google.com/sdk/docs/install))
- `terraform` >= 1.7 ([install](https://developer.hashicorp.com/terraform/install))
- `uv` ([install](https://docs.astral.sh/uv/))
- Git access to this repo + Google account with `roles/run.invoker` on staging research-app

## 2. First clone

```bash
git clone <repo-url> Data_Platform_2
cd Data_Platform_2
uv sync --all-extras
uv run pre-commit install
uv run pytest -m unit
# Expected: ~175 passed
```

## 3. GCP auth

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project vn-market-platform-staging
gcloud config set project vn-market-platform-staging
```

## 4. First SQL query

```bash
bq query --use_legacy_sql=false \
  "SELECT * FROM \`vn-market-platform-staging.vnmarket.v_top_of_book\` LIMIT 5"
```

## 5. First SDK call

```python
import vnmarket as vm
client = vm.Client(env="staging")
df = client.daily(["VNM"], start="2024-01-02", end="2024-01-31")
print(df.head())
```

(Or run `notebooks/00-quickstart.ipynb` cell-by-cell.)

## 6. Streamlit research-app

Visit `https://research-app-xxx.run.app` (URL from `terraform output research_app_url`). Sign in with the Google account that has `roles/run.invoker`.

## 7. Where things live

| Concern | Location |
|---|---|
| Architecture spec | `docs/01-architecture.md` |
| Implementation plan | `plans/260425-1531-vn-market-data-platform/` |
| Workflows YAML | `infra/workflows/` |
| Terraform | `infra/{bootstrap,envs,modules,wif}/` |
| Python services | `src/{publisher,writers,batch,curate,alerter,research_app,ops,vnmarket}/` |
| Tests | `tests/{unit,integration,contract,e2e}/` |
| SQL DDLs | `sql/{schemas,views}/` |
| Calendar | `infra/calendar/` |
| Symbol manifests | `infra/symbols/` |

## 8. Common dev tasks

| Task | Command |
|---|---|
| Run unit tests | `uv run pytest -m unit` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Update deps | `uv sync --all-extras` |
| Apply infra | `cd infra/envs/staging && terraform apply` |
| Build images | `./scripts/build-and-push.sh staging` |
| Trigger workflow | `gcloud workflows run eod-pipeline ...` (see docs/03) |
| Read DLQ | `gsutil cat gs://vn-market-lake-staging/_ops/dlq-export/...` |

## 9. When something breaks

See `docs/05-runbook-incident.md`.

## 10. v1 backlog

Tracked in `docs/00-overview.md` "Open questions" section.
