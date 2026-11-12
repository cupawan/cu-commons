# Changelog

## 1.1.0 — 2026-11-12
Added (pieces worth keeping from the retired Telegram_Bots / ETLFS_Pipelines / Python_Packages repos):
- `TelegramBot.download_file()`, `send_photo()`, `send_audio()`; `parse_update()` now reports photos, voice notes and captions.
- `apis.strava.authorization_url()` and `exchange_code()` for the one-time OAuth step.
- `aws.s3`: `put_bytes/get_bytes`, `put_json/get_json`, `share_link` (presigned download URL).
- `apis.sheets.Sheet` (Google Sheets via a service account; extra `sheets`).

## 1.0.0 — 2026-11-12
First public release, rewritten from the `commons` package inside `automations`.
- Clients take credentials explicitly (`from_env()` optional); no hidden configuration reads.
- New: shared HTTP helper with retries, `TelegramBot` JSON client + `parse_update`, `SmtpEmail`, `TelegramAlerter`,
  `lambda_handler`, `GarminPersonal` (official Personal API) with typed metric helpers, `StravaClient` with token
  rotation hook, Open-Meteo helpers, `Postgres.migrate()` / `fetch()`.
- Dropped: unofficial Garmin login, OpenWeatherMap client, legacy report formatter, `pytz`.
