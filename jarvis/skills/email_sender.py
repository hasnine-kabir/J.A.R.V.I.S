import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jarvis.skills.base import BaseSkill, Tool


class EmailSenderSkill(BaseSkill):
    name = "email_sender"
    description = "Send emails from the user's Gmail account via SMTP"
    tools = [
        Tool(
            name="send_email",
            description="Send an email. Confirm recipient, subject and body with the user first.",
            parameters={
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Subject line"},
                "body": {"type": "string", "description": "Plain-text body"},
            },
            required=["to", "subject", "body"],
            confirm=True,
        ),
    ]

    def __init__(self, smtp_email: str = "", smtp_password: str = ""):
        self._email = smtp_email
        self._password = smtp_password

    def setup(self, config, memory) -> None:
        self._email = self._email or config.smtp_email
        self._password = self._password or config.smtp_password

    def execute(self, action: str, args: dict) -> str:
        if action == "send_email":
            return self._send(args["to"], args["subject"], args["body"])
        raise ValueError(f"Unknown action: {action}")

    def _send(self, to: str, subject: str, body: str) -> str:
        if not self._email or not self._password:
            return ("Email is not configured. Set SMTP_EMAIL and SMTP_PASSWORD "
                    "(a Gmail app password) in the .env file.")
        msg = MIMEMultipart()
        msg["From"] = self._email
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
            try:
                server.ehlo()
                server.starttls()
                server.login(self._email, self._password)
                server.sendmail(self._email, [to], msg.as_string())
            finally:
                server.close()
        except Exception as e:
            return f"Failed to send email: {e}"
        return f"Email sent to {to}."
