# VN Trading Calendar

JSON-encoded trading calendar per year. Source of truth in this repo; runtime read at `gs://vn-market-lake-{env}/_ops/calendar/{year}.json` (deployed by Terraform).

## File format

See `schema.json` (JSON Schema draft-07).

## Data provenance

- **Statutory holidays** are derived from Vietnamese Labour Code Article 112 (Tet, Hung Kings, Reunification, Labour Day, National Day) plus the annual government Decision specifying substitute days when a holiday falls on a weekend.
- **Trading days** are computed as `weekdays(year) - holidays(year)` and are not independently sourced. HOSE/HNX may declare ad-hoc closures (e.g., system maintenance) that this scaffold does NOT capture; operator must add such dates to the `holidays` array.
- **Lunar holidays** (Tet, Hung Kings) shift each year. Dates here through 2025 reflect officially-decreed dates. **2026 dates are best-known as of plan authorship; operator MUST verify against the official decree before relying on them.**

## Update procedure

1. Identify any new holiday or substitute-day decision (Vietnam Government Decision, typically published in Q4 of preceding year).
2. Edit the corresponding `vn-trading-days-{year}.json` — update `holidays` and recompute `trading_days`.
3. Validate locally:
   ```bash
   uv run python -c "import json, jsonschema; jsonschema.validate(json.load(open('infra/calendar/vn-trading-days-2026.json')), json.load(open('infra/calendar/schema.json')))"
   ```
4. Submit PR; the calendar deploys via Terraform on staging-merge.

## Coverage

| Year | Trading days | Notes |
|---|---|---|
| 2021 | 250 | Full data |
| 2022 | 249 | Full data |
| 2023 | 249 | Full data |
| 2024 | 250 | Full data |
| 2025 | 248 | Full data |
| 2026 | 251 | Best-known; operator to confirm |
