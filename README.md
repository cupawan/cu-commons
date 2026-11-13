# cu-commons

Small, portable Python clients and helpers for personal automations — Telegram bots, GitHub repo files, email, Postgres (Neon), MongoDB, Garmin's official Personal API, Strava, Open-Meteo weather, and AWS Lambda plumbing.

- **Explicit configuration:** every client takes its credentials as arguments; `from_env()` is an optional shortcut. Nothing reads secrets behind your back.
- **Resilient by default:** HTTP calls have timeouts and retry on rate limits / server errors (honouring `Retry-After`); Neon's scale-to-zero wake-up is retried.
- **Light:** the core needs only `requests`; heavier dependencies are opt-in extras.

## Install

```bash
pip install "cu-commons[all] @ git+https://github.com/cupawan/cu-commons@v1.2.0"
# or only what you need:  cu-commons[db]  cu-commons[garmin]  cu-commons[aws]  cu-commons[sheets]
```
Requires Python 3.12+.

## Modules

| Module | What it gives you | Extra |
|---|---|---|
| `cu_commons.telegram` | `TelegramBot` (send/edit messages, keyboards, documents/photos/audio, `download_file`, webhooks), `parse_update()` | — |
| `cu_commons.email` | `SmtpEmail` (HTML, attachments; Gmail app-password defaults) | — |
| `cu_commons.alerts` | `TelegramAlerter` for errors and notices | — |
| `cu_commons.aws` | `lambda_handler` decorator (SSM secrets, alerts, error handling), `event_kind()`; `aws.s3` put/get bytes or JSON, `share_link` | `aws` |
| `cu_commons.config` | `get()`, `load_ssm()`, `put_ssm()` | `aws` |
| `cu_commons.db.postgres` | `Postgres` (TLS, wake-up retries, `fetch`, `execute`, `read_df`, read-only queries, `migrate()`) | `db` |
| `cu_commons.db.mongo` | `Mongo` (insert, upsert, find, `ensure_indexes`) | `db` |
| `cu_commons.apis.garmin` | `GarminPersonal` (official Personal API) + `sleep_metrics`, `hrv_metrics`, `daily_metrics` | `garmin` |
| `cu_commons.apis.strava` | `StravaClient` with automatic token refresh and an `on_refresh` hook; `authorization_url()` / `exchange_code()` for setup | — |
| `cu_commons.apis.github` | `GitHubRepo` (read a file, commit a change; `update_text` / `update_json` re-apply on concurrent edits) | — |
| `cu_commons.apis.sheets` | `Sheet` (Google Sheets: records, append, write, clear) | `sheets` |
| `cu_commons.apis.openmeteo` | `forecast()`, `air_quality()`, `hourly_values()` (no API key) | — |
| `cu_commons.dates`, `utils`, `http` | IST-aware dates, durations/pace, nested-JSON lookup, JSON over HTTP with retries | — |

## Examples

```python
from cu_commons.telegram import TelegramBot

bot = TelegramBot(token)
bot.send_message(chat_id, "Hello", reply_markup=bot.inline_keyboard([[("👍", "vote:up"), ("👎", "vote:down")]]))
```

```python
from cu_commons.apis.garmin import GarminPersonal, sleep_metrics, hrv_metrics

garmin = GarminPersonal(api_key)                  # key from connect.garmin.com/app/settings/personalApiToken
sleep = sleep_metrics(garmin.sleep("2026-11-12"))
hrv = hrv_metrics(garmin.hrv("2026-11-12"))
print(sleep.seconds, sleep.score, hrv.last_night, hrv.status)
```

```python
from cu_commons.apis.strava import StravaClient
from cu_commons.config import put_ssm

strava = StravaClient(client_id, client_secret, refresh_token,
                      on_refresh=lambda token: put_ssm("StravaRefreshToken", token, "/myapp/prod/"))
run = strava.latest("Run")
```

```python
from cu_commons.aws import lambda_handler

@lambda_handler("my-service")        # loads SSM_PREFIX secrets, alerts via AlertsBotToken/SelfTgChatId if set
def handler(event, context):
    ...
```

```python
from cu_commons.apis.github import GitHubRepo

repo = GitHubRepo(token, "cupawan/PFOS", branch="dev")   # fine-grained token: this repo, Contents read+write
repo.update_json("config/lending.json",
                 lambda d: d["entries"].append({"date": "2026-11-13", "person": "Raman", "type": "lent", "amount": 92}),
                 "exec: Raman 92 (via bot)")              # retries if you pushed in between
```

## Development

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
ruff check . && pytest -q
```

Releases are git tags (`v1.0.0`, `v1.1.0`, …). Consumers pin a tag; see `CHANGELOG.md` before upgrading.

## Licence
MIT
