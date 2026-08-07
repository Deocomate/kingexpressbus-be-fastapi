"""Mail transport abstraction (Gmail SMTP + test-recording double)."""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any, Protocol

import aiosmtplib

from app.core.config import Settings

logger = logging.getLogger(__name__)


class MailSender(Protocol):
    async def send(self, *, to: list[str], subject: str, html: str) -> None: ...


class SmtpMailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, *, to: list[str], subject: str, html: str) -> None:
        if not self._settings.mail_username or not self._settings.mail_password:
            logger.info(
                "SMTP skipped (missing MAIL_USERNAME/MAIL_PASSWORD)",
                extra={"to": to, "subject": subject},
            )
            return

        message = EmailMessage()
        message["From"] = (
            f"{self._settings.mail_from_name} <{self._settings.mail_from}>"
        )
        message["To"] = ", ".join(to)
        message["Subject"] = subject
        message.set_content(html, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=self._settings.mail_host,
            port=self._settings.mail_port,
            username=self._settings.mail_username,
            password=self._settings.mail_password,
            start_tls=self._settings.mail_use_tls,
        )


class RecordingMailSender:
    """Test double that records sends."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, *, to: list[str], subject: str, html: str) -> None:
        self.sent.append({"to": to, "subject": subject, "html": html})


_sender: MailSender | None = None


def get_mail_sender(settings: Settings) -> MailSender:
    if _sender is not None:
        return _sender
    return SmtpMailSender(settings)


def set_mail_sender(sender: MailSender | None) -> None:
    global _sender
    _sender = sender
