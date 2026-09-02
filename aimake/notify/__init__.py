"""Outbound notifications: Slack, Discord, email."""

from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

from aimake.config.schema import (
    DiscordNotifyConfig,
    EmailNotifyConfig,
    NotificationsConfig,
    SlackNotifyConfig,
)


def _post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


class Notifier:
    """Dispatch notifications based on aimake.yaml notifications block."""

    def __init__(self, config: NotificationsConfig | None) -> None:
        self.config = config or NotificationsConfig()

    def notify(
        self,
        event: str,
        title: str,
        body: str,
        *,
        fields: dict[str, Any] | None = None,
    ) -> list[str]:
        """Send for an event: fail | success | quality_gate | cost_spike.

        Returns list of channel labels that were contacted.
        """
        sent: list[str] = []
        text = self._format(title, body, fields)
        if self.config.slack and self._want(self.config.slack, event):
            if self._slack(self.config.slack, text):
                sent.append("slack")
        if self.config.discord and self._want(self.config.discord, event):
            if self._discord(self.config.discord, text):
                sent.append("discord")
        if self.config.email and self._want(self.config.email, event):
            if self._email(self.config.email, title, text):
                sent.append("email")
        return sent

    @staticmethod
    def _want(cfg: Any, event: str) -> bool:
        if not getattr(cfg, "enabled", False):
            return False
        mapping = {
            "fail": "on_fail",
            "success": "on_success",
            "quality_gate": "on_quality_gate",
            "cost_spike": "on_cost_spike",
        }
        attr = mapping.get(event)
        return bool(attr and getattr(cfg, attr, False))

    @staticmethod
    def _format(title: str, body: str, fields: dict[str, Any] | None) -> str:
        lines = [f"*{title}*" if title else "", body]
        if fields:
            for k, v in fields.items():
                lines.append(f"• {k}: {v}")
        return "\n".join(x for x in lines if x)

    def _slack(self, cfg: SlackNotifyConfig, text: str) -> bool:
        url = os.environ.get(cfg.webhook_env, "").strip()
        if not url:
            return False
        try:
            _post_json(url, {"text": text})
            return True
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _discord(self, cfg: DiscordNotifyConfig, text: str) -> bool:
        url = os.environ.get(cfg.webhook_env, "").strip()
        if not url:
            return False
        try:
            _post_json(url, {"content": text[:1900]})
            return True
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _email(self, cfg: EmailNotifyConfig, subject: str, body: str) -> bool:
        if not cfg.to_addrs:
            return False
        msg = EmailMessage()
        msg["Subject"] = subject or "aimake notification"
        msg["From"] = cfg.from_addr
        msg["To"] = ", ".join(cfg.to_addrs)
        msg.set_content(body.replace("*", ""))
        try:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                if cfg.use_tls:
                    smtp.starttls()
                user = os.environ.get(cfg.smtp_user_env or "", "") if cfg.smtp_user_env else ""
                password = (
                    os.environ.get(cfg.smtp_password_env or "", "")
                    if cfg.smtp_password_env
                    else ""
                )
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
            return True
        except (OSError, smtplib.SMTPException):
            return False
