"""Send email over SMTP (defaults suit Gmail with an app password)."""
import mimetypes
import os
import smtplib
from email.message import EmailMessage


class SmtpEmail:
    def __init__(self, user: str, password: str, host: str = "smtp.gmail.com", port: int = 465,
                 sender_name: str | None = None):
        self.user, self.password, self.host, self.port = user, password, host, port
        self.sender = f"{sender_name} <{user}>" if sender_name else user

    @classmethod
    def from_env(cls, user_var: str = "SMTP_USER", password_var: str = "SMTP_PASSWORD", **kwargs):
        return cls(os.environ[user_var], os.environ[password_var], **kwargs)

    def build(self, to: str | list[str], subject: str, body: str, html: bool = False,
              attachments: list[tuple[str, bytes]] | None = None) -> EmailMessage:
        msg = EmailMessage()
        msg["From"], msg["Subject"] = self.sender, subject
        msg["To"] = ", ".join(to) if isinstance(to, list) else to
        msg.set_content("This message is HTML; please view it in an HTML-capable client.")
        if html:
            msg.add_alternative(body, subtype="html")
        else:
            msg.set_content(body)
        for filename, content in attachments or []:
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
        return msg

    def send(self, to, subject: str, body: str, html: bool = False, attachments=None) -> None:
        msg = self.build(to, subject, body, html, attachments)
        with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as smtp:
            smtp.login(self.user, self.password)
            smtp.send_message(msg)
