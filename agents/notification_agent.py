"""
agents/notification_agent.py — Sends email report after each run
"""
import logging
from datetime import datetime

logger = logging.getLogger("NotificationAgent")


class NotificationAgent:
    def __init__(self, config):
        self.cfg = config

    def send(self, result: dict):
        if not self.cfg.notification_email:
            self._log_result(result)
            return
        try:
            self._send_email(result)
        except Exception as e:
            logger.warning(f"Email failed: {e}")

    def _send_email(self, result: dict):
        import sendgrid
        from sendgrid.helpers.mail import Mail
        status_emoji = "✅" if result["status"] == "success" else "❌"
        subject = f"{status_emoji} YouTube Bot | {result.get('topic','')[:40]} | {datetime.now().strftime('%d %b %Y')}"
        body = f"Status: {result['status']}\nURL: {result.get('youtube_url','N/A')}\nError: {result.get('error','None')}"
        message = Mail(from_email="bot@yourdomain.com", to_emails=self.cfg.notification_email,
                      subject=subject, plain_text_content=body)
        sg = sendgrid.SendGridAPIClient(api_key=self.cfg.sendgrid_api_key)
        sg.send(message)

    def _log_result(self, result: dict):
        logger.info(f"=== RUN COMPLETE === {result}")
