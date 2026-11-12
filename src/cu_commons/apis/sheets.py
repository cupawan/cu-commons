"""Google Sheets via a service account (gspread). Install cu-commons[sheets].

Setup once: Google Cloud -> create a service account -> JSON key; share the spreadsheet with the
service account's email (Editor). Pass the JSON (dict or string) as `credentials`.
"""
import json
import os


class Sheet:
    def __init__(self, credentials: dict | str, spreadsheet_id: str, worksheet: str | None = None, client=None):
        if client is None:
            import gspread

            creds = json.loads(credentials) if isinstance(credentials, str) else credentials
            client = gspread.service_account_from_dict(creds)
        book = client.open_by_key(spreadsheet_id)
        self.ws = book.worksheet(worksheet) if worksheet else book.sheet1

    @classmethod
    def from_env(cls, spreadsheet_id: str, worksheet: str | None = None, credentials_var: str = "GoogleServiceAccountJson"):
        return cls(os.environ[credentials_var], spreadsheet_id, worksheet)

    def records(self) -> list[dict]:
        """Rows as dicts keyed by the header row."""
        return self.ws.get_all_records()

    def append(self, rows: list[list]) -> None:
        self.ws.append_rows(rows, value_input_option="USER_ENTERED")

    def write(self, values: list[list], start: str = "A1") -> None:
        self.ws.update(range_name=start, values=values, value_input_option="USER_ENTERED")

    def clear(self) -> None:
        self.ws.clear()
