"""
Gmail Connector.
Supports reading unread emails, searching messages, drafting, and sending emails.
Uses secure IMAP/SMTP with App Password (zero-overhead) with support for Google APIs.
"""

import imaplib
import smtplib
import email
import httpx
from email.message import EmailMessage
from email.header import decode_header
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .base import BaseConnector, ActionResult
from ..config.config import config

import logging

logger = logging.getLogger("SocialCommander.Gmail")
executor = ThreadPoolExecutor(max_workers=5)


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
        return bool((self.email_address and self.app_password) or config.RESEND_API_KEY or config.BREVO_API_KEY)

    def _sync_test_connection(self) -> ActionResult:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", timeout=15) as mail:
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
        try:
            return await asyncio.wait_for(loop.run_in_executor(executor, self._sync_test_connection), timeout=25.0)
        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                platform="gmail",
                action="test_connection",
                message="Gmail connection check timed out (15s).",
                error="TIMEOUT"
            )

    def _sync_list_unread(self, max_results: int = 5) -> ActionResult:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", timeout=15) as mail:
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
        try:
            return await asyncio.wait_for(loop.run_in_executor(executor, self._sync_list_unread, max_results), timeout=30.0)
        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                platform="gmail",
                action="list_unread",
                message="Listing unread emails timed out.",
                error="TIMEOUT"
            )

    def _sync_send_email(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> ActionResult:
        try:
            if not to or not to.strip():
                return ActionResult(
                    success=False,
                    platform="gmail",
                    action="send_email",
                    message="Recipient email address is missing.",
                    error="MISSING_RECIPIENT"
                )

            msg = EmailMessage()
            msg["Subject"] = subject or "No Subject"
            msg["From"] = self.email_address
            msg["To"] = to.strip()
            msg.set_content(body or "")

            if html_body:
                msg.add_alternative(html_body, subtype="html")

            # Try Port 587 with STARTTLS first (standard for cloud environments like Render)
            sent = False
            last_error = None

            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                    smtp.login(self.email_address, self.app_password)
                    smtp.send_message(msg)
                    sent = True
                    logger.info(f"Email sent successfully to {to} via smtp.gmail.com:587 (STARTTLS)")
            except Exception as e587:
                last_error = e587
                logger.warning(f"SMTP 587 failed ({e587}), falling back to 465 (SSL)...")

            # Fallback to Port 465 with SSL if 587 was blocked
            if not sent:
                try:
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
                        smtp.login(self.email_address, self.app_password)
                        smtp.send_message(msg)
                        sent = True
                        logger.info(f"Email sent successfully to {to} via smtp.gmail.com:465 (SSL)")
                except Exception as e465:
                    last_error = e465
                    logger.error(f"SMTP 465 also failed: {e465}")

            if sent:
                return ActionResult(
                    success=True,
                    platform="gmail",
                    action="send_email",
                    message=f"Email successfully sent to {to}!",
                    data={"to": to, "subject": subject}
                )
            else:
                err_str = str(last_error)
                is_port_block = any(k in err_str.lower() for k in ["timed out", "timeout", "refused", "111", "11001", "network is unreachable"])
                if is_port_block:
                    msg = (
                        f"⚠️ Outbound SMTP ports (587/465) are blocked on Render Free Tier.\n\n"
                        f"💡 Quick Fix: Add RESEND_API_KEY to your Render Environment Variables (free at resend.com - takes 1 min, 3,000 free emails/month)."
                    )
                else:
                    msg = f"Failed to send email to {to}: {err_str}"

                return ActionResult(
                    success=False,
                    platform="gmail",
                    action="send_email",
                    message=msg,
                    error=err_str
                )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message=f"Failed to send email to {to}: {str(e)}",
                error=str(e)
            )

    async def _send_via_resend(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> ActionResult:
        """Sends an email via Resend HTTP REST API over port 443 (immune to cloud SMTP port blocking)."""
        try:
            from_addr = config.EMAIL_FROM or "SocialCommander <onboarding@resend.dev>"
            headers = {
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": from_addr,
                "to": [to.strip()],
                "subject": subject or "No Subject",
                "text": body or "",
                "html": html_body or (body.replace("\n", "<br>") if body else "")
            }
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post("https://api.resend.com/emails", headers=headers, json=payload)
                data = res.json()
                if res.status_code in (200, 201) and "id" in data:
                    email_id = data["id"]
                    logger.info(f"Email successfully sent to {to} via Resend HTTP API (ID: {email_id})")
                    return ActionResult(
                        success=True,
                        platform="gmail",
                        action="send_email",
                        message=f"Email successfully sent to {to}! (via Resend HTTPS API)",
                        data={"to": to, "subject": subject, "id": email_id}
                    )
                else:
                    err_msg = data.get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="gmail",
                        action="send_email",
                        message=f"Failed to send email via Resend: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message=f"Exception sending via Resend: {str(e)}",
                error=str(e)
            )

    async def _send_via_brevo(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> ActionResult:
        """Sends an email via Brevo REST API over HTTPS port 443 (free, sends to any recipient)."""
        try:
            sender_email = self.email_address or "yacquubqaxwe@gmail.com"
            headers = {
                "api-key": config.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "sender": {"name": "SocialCommander", "email": sender_email},
                "to": [{"email": to.strip()}],
                "subject": subject or "No Subject",
                "textContent": body or "",
                "htmlContent": html_body or (body.replace("\n", "<br>") if body else "")
            }
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post("https://api.brevo.com/v3/smtp/email", headers=headers, json=payload)
                data = res.json()
                if res.status_code in (200, 201) and "messageId" in data:
                    msg_id = data["messageId"]
                    logger.info(f"Email successfully sent to {to} via Brevo HTTP API (ID: {msg_id})")
                    return ActionResult(
                        success=True,
                        platform="gmail",
                        action="send_email",
                        message=f"Email successfully sent to {to}! (via Brevo HTTPS API)",
                        data={"to": to, "subject": subject, "id": msg_id}
                    )
                else:
                    err_msg = data.get("message", res.text)
                    return ActionResult(
                        success=False,
                        platform="gmail",
                        action="send_email",
                        message=f"Failed to send email via Brevo: {err_msg}",
                        error=err_msg
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message=f"Exception sending via Brevo: {str(e)}",
                error=str(e)
            )

    async def send_email(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> ActionResult:
        """Sends an email via Brevo/Resend HTTP API (if configured) or Gmail SMTP with dual-port fallback."""
        if config.BREVO_API_KEY:
            return await self._send_via_brevo(to, subject, body, html_body)

        if config.RESEND_API_KEY:
            return await self._send_via_resend(to, subject, body, html_body)

        if not self.is_configured():
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message="Gmail credentials, BREVO_API_KEY, or RESEND_API_KEY not configured.",
                error="UNCONFIGURED"
            )
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(executor, self._sync_send_email, to, subject, body, html_body),
                timeout=35.0
            )
        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                platform="gmail",
                action="send_email",
                message=(
                    f"⚠️ Gmail SMTP timed out (35s) because Render Free Tier blocks outbound SMTP ports (587 & 465).\n\n"
                    f"💡 1-Minute Free Fix: Add BREVO_API_KEY or RESEND_API_KEY to your Render Environment Variables.\n"
                    f"• Brevo (brevo.com): 300 free emails/day to any recipient, no domain verification needed.\n"
                    f"• Resend (resend.com): 3,000 free emails/month."
                ),
                error="RENDER_PORT_BLOCKED"
            )

    def _sync_create_draft(self, to: str, subject: str, body: str) -> ActionResult:
        """Appends a message to the Gmail [Gmail]/Drafts folder."""
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.email_address
            msg["To"] = to
            msg.set_content(body)

            with imaplib.IMAP4_SSL("imap.gmail.com", timeout=15) as mail:
                mail.login(self.email_address, self.app_password)
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
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(executor, self._sync_create_draft, to, subject, body),
                timeout=25.0
            )
        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                platform="gmail",
                action="create_draft",
                message="Creating Gmail draft timed out.",
                error="TIMEOUT"
            )
