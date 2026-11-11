# Changelog

## 1.0.0 — 2026-11-12
First public release, rewritten from the `commons` package inside `automations`.
- Clients take credentials explicitly (`from_env()` optional); no hidden configuration reads.
- New: shared HTTP helper with retries, `TelegramBot` JSON client + `parse_update`, `SmtpEmail`, `TelegramAlerter`,
  `lambda_handler`, `GarminPersonal` (official Personal API) with typed metric helpers, `StravaClient` with token
  rotation hook, Open-Meteo helpers, `Postgres.migrate()` / `fetch()`.
- Dropped: unofficial Garmin login, OpenWeatherMap client, legacy report formatter, `pytz`.
