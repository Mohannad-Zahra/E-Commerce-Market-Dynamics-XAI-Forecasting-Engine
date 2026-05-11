"""
email_service.py
================
Database-driven B2C Action Layer.
Queries the daily_recommendations table and dispatches emails using Resend.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List

import resend
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from dotenv import load_dotenv

from database.models import SessionLocal, DailyRecommendation, Subscriber, EmailAuditLog

load_dotenv()

RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "re_R7Dqobmv_LZzNYXVzpMJDGZ3FUeZ5qJ7y")
EMAIL_FROM      = os.getenv("EMAIL_FROM",      "onboarding@resend.dev")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Laptop Deal Alerts")
resend.api_key = RESEND_API_KEY

logger = logging.getLogger(__name__)

def _build_html(recommendations: List[DailyRecommendation], recipient_name: str = "") -> str:
    """Render a clean HTML email body from the daily recommendation records."""
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi there,"
    today     = datetime.now(timezone.utc).strftime("%B %d, %Y")

    cards_html = ""
    for rec in recommendations:
        model       = rec.model or "N/A"
        r_score     = rec.r_score or "N/A"
        cls         = rec.classification or "N/A"
        confidence  = rec.confidence or "N/A"
        explanation = rec.llm_explanation or "No explanation available."
        
        # We format score gracefully if it's a float
        score_str = f"{r_score:.1f}" if isinstance(r_score, float) else str(r_score)

        cards_html += f"""
        <div style="background:#f9f9f9;border-left:4px solid #4CAF50;
                    margin:16px 0;padding:16px;border-radius:4px;">
          <p style="margin:0 0 6px 0;font-size:13px;color:#555;">
            <strong>Product:</strong>
            <a href="{model}" style="color:#1a73e8;">{model[:80]}{'…' if len(model) > 80 else ''}</a>
          </p>
          <p style="margin:0 0 6px 0;font-size:13px;color:#555;">
            <strong>Score:</strong> {score_str} &nbsp;|&nbsp;
            <strong>State:</strong> {cls} &nbsp;|&nbsp;
            <strong>Confidence:</strong> {confidence}
          </p>
          <p style="margin:0;font-size:14px;color:#333;line-height:1.6;">
            {explanation}
          </p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily Laptop Deals – {today}</title></head>
<body style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:20px;color:#333;">

  <div style="background:#1a73e8;padding:20px;border-radius:6px 6px 0 0;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:22px;">🔔 Daily Laptop Deal Alert</h1>
    <p style="color:#e8f0fe;margin:6px 0 0 0;font-size:13px;">{today} · Autonomous Recommendation Engine</p>
  </div>

  <div style="background:#fff;padding:24px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 6px 6px;">
    <p style="font-size:15px;">{greeting}</p>
    <p style="font-size:14px;color:#555;">
      Here are today's top laptop deals identified by our market analysis engine.
    </p>

    {cards_html}

    <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
    <p style="font-size:12px;color:#999;text-align:center;">
      You're receiving this because you opted in to Laptop Deal Alerts.
    </p>
  </div>

</body>
</html>"""
    return html

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _send_via_resend_with_retry(to_email: str, subject: str, html_body: str) -> str:
    """
    Sends email via Resend with exponential backoff on failure.
    Returns the Resend ID on success. Raises exception on failure.
    """
    r = resend.Emails.send({
        "from":    f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
        "to":      to_email,
        "subject": subject,
        "html":    html_body,
    })
    
    if not r or not r.get("id"):
        raise Exception(f"Resend returned unexpected response: {r}")
        
    return r.get("id")

def dispatch_pending_emails() -> dict:
    """
    Query database for pending approved recommendations, build the payload,
    dispatch emails to subscribers, and track the audit log.
    """
    db = SessionLocal()
    try:
        # 1. Fetch unemailed, approved recommendations
        pending_recs = db.query(DailyRecommendation).filter(
            DailyRecommendation.status == "Approved",
            DailyRecommendation.emailed == False
        ).all()

        if not pending_recs:
            logger.info("No pending approved recommendations to dispatch.")
            return {"sent": 0, "failed": 0}

        # 2. Fetch active subscribers
        subscribers = db.query(Subscriber).filter(
            Subscriber.category == "laptop",
            Subscriber.active == 1
        ).all()

        if not subscribers:
            logger.info("No active subscribers found.")
            return {"sent": 0, "failed": 0}

        today = datetime.now(timezone.utc).strftime("%B %d, %Y")
        subject = f"🔔 Daily Laptop Deals – {today}"

        sent_count = 0
        failed_count = 0
        
        # 3. Dispatch loop
        for sub in subscribers:
            html_body = _build_html(pending_recs, recipient_name=sub.name)
            
            try:
                # Attempt to send with retry
                resend_id = _send_via_resend_with_retry(sub.email, subject, html_body)
                status = "SUCCESS"
                error_msg = f"Resend ID: {resend_id}"
                sent_count += 1
                logger.info(f"Successfully sent email to {sub.email}")
            except Exception as e:
                status = "FAILED"
                error_msg = str(e)
                failed_count += 1
                logger.error(f"Failed to send email to {sub.email}: {error_msg}")

            # Audit log for each recommendation & subscriber
            for rec in pending_recs:
                audit = EmailAuditLog(
                    recommendation_id=rec.id,
                    recipient_email=sub.email,
                    status=status,
                    error_message=error_msg
                )
                db.add(audit)

        # 4. Update recommendations flag to prevent duplicates
        now = datetime.now(timezone.utc)
        for rec in pending_recs:
            rec.emailed = True
            rec.dispatched_at = now
            if failed_count > 0 and sent_count == 0:
                rec.email_error = "Failed to send to any subscriber."

        db.commit()
        return {"sent": sent_count, "failed": failed_count}

    except Exception as e:
        logger.error(f"Database/Dispatch error: {e}")
        db.rollback()
        return {"sent": 0, "failed": 0}
    finally:
        db.close()
