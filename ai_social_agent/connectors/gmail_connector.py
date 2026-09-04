"""
Gmail Connector.
Supports reading unread emails, searching messages, drafting, and sending emails.
Uses secure IMAP/SMTP with App Password (zero-overhead) with support for Google APIs.
"""

import imaplib
import smtplib
import email
from email.message import EmailMessage
from email.header import decode_header
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .base import BaseConnector, ActionResult
from ..config.config import config

executor = ThreadPoolExecutor(max_workers=3)


def _decode_mime_words(s: str) -> str:
    """Decodes MIME encoded header strings into unicode."""
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    result = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result)


class GmailConnector(BaseConnector):
    def __init__(self):
        super().__init__("gmail")
        self.email_address = config.GMAIL_EMAIL
        self.app_password = config.GMAIL_APP_PASSWORD.replace(" ", "")

    def is_configured(self) -> bool:
        return bool(self.email_address and self.app_password)

    def _sync_test_connection(self) -> ActionResult:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
                mail.login(self.email_address, self.app_password)
                mail.select("INBOX")
                status, data = mail.search(None, "UNSEEN")
                unread_count = len(data[0].split()) if status == "OK" and data[0] else 0
                return ActionResult(
                    success=True,
                    platform="gmail",
                    action="test_connection",
                    message=f"Connected to Gmail: {self.email_address} ({unread_count} unread emails)",
                    data={"unread_count": unread_count, "email": self.email_address}
                )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="test_connection",
                message=f"Gmail authentication failed for {self.email_address}.",
                error=str(e)
            )

    async def test_connection(self) -> ActionResult:
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="gmail",
                action="test_connection",
                message="Gmail credentials (GMAIL_EMAIL and GMAIL_APP_PASSWORD) not configured.",
                error="UNCONFIGURED"
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._sync_test_connection)

    def _sync_list_unread(self, max_results: int = 5) -> ActionResult:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
                mail.login(self.email_address, self.app_password)
                mail.select("INBOX")
                status, data = mail.search(None, "UNSEEN")
                if status != "OK" or not data[0]:
                    return ActionResult(
                        success=True,
                        platform="gmail",
                        action="list_unread",
                        message="Inbox has 0 unread messages.",
                        data={"emails": []}
                    )

                ids = data[0].split()
                latest_ids = ids[-max_results:]
                latest_ids.reverse()  # newest first

                emails: List[Dict[str, Any]] = []
                for num in latest_ids:
                    _, msg_data = mail.fetch(num, "(RFC822.HEADER BODY.PEEK[TEXT])")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject = _decode_mime_words(msg.get("Subject", "(No Subject)"))
                            from_ = _decode_mime_words(msg.get("From", "(Unknown Sender)"))
                            date_ = msg.get("Date", "")
                            
                            # Snippet extraction
                            body_text = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            body_text = payload.decode(errors="replace")[:300]
                                            break
                            else:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    body_text = payload.decode(errors="replace")[:300]

                            emails.append({
                                "id": num.decode(),
                                "from": from_,
                                "subject": subject,
                                "date": date_,
                                "snippet": body_text.strip().replace("\r\n", " ").replace("\n", " ")[:200]
                            })

                return ActionResult(
                    success=True,
                    platform="gmail",
                    action="list_unread",
                    message=f"Retrieved {len(emails)} unread email(s).",
                    data={"emails": emails}
                )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="list_unread",
                message="Failed to list unread Gmail messages.",
                error=str(e)
            )

    async def list_unread(self, max_results: int = 5) -> ActionResult:
        """Fetches latest unread emails."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="gmail",
                action="list_unread",
                message="Gmail not configured.",
                error="UNCONFIGURED"
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._sync_list_unread, max_results)

    def _sync_send_email(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> ActionResult:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.email_address
            msg["To"] = to
            msg.set_content(body)

            if html_body:
                msg.add_alternative(html_body, subtype="html")

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.email_address, self.app_password)
                smtp.send_message(msg)

            return ActionResult(
                success=True,
                platform="gmail",
                action="send_email",
                message=f"Email successfully sent to {to}!",
                data={"to": to, "subject": subject}
            )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message=f"Failed to send email to {to}.",
                error=str(e)
            )

    async def send_email(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> ActionResult:
        """Sends an email via Gmail SMTP."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message="Gmail credentials not configured.",
                error="UNCONFIGURED"
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._sync_send_email, to, subject, body, html_body)

    def _sync_create_draft(self, to: str, subject: str, body: str) -> ActionResult:
        """Appends a message to the Gmail [Gmail]/Drafts folder."""
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.email_address
            msg["To"] = to
            msg.set_content(body)

            with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
                mail.login(self.email_address, self.app_password)
                # Gmail drafts folder is typically "[Gmail]/Drafts"
                mail.append('"[Gmail]/Drafts"', "", imaplib.Time2Internaldate(email.utils.parsedate_to_datetime(email.utils.formatdate())), msg.as_bytes())

            return ActionResult(
                success=True,
                platform="gmail",
                action="create_draft",
                message=f"Draft email to {to} created in Gmail Drafts folder.",
                data={"to": to, "subject": subject}
            )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="create_draft",
                message="Failed to create Gmail draft.",
                error=str(e)
            )

    async def create_draft(self, to: str, subject: str, body: str) -> ActionResult:
        """Saves an email draft to Gmail."""
        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="gmail",
                action="create_draft",
                message="Gmail credentials not configured.",
                error="UNCONFIGURED"
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._sync_create_draft, to, subject, body)
