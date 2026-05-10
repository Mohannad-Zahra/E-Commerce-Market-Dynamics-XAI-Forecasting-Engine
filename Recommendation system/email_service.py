"""
email_service.py
================
Step 5 of the Phase 4 pipeline: Autonomous Email Notification.

Queries the subscribers table for users opted into Laptop alerts,
formats a clean HTML email from today's daily_recommendations, and
dispatches it via the Resend API.

Requires:
    pip install resend

Configuration
-------------
Set RESEND_API_KEY and EMAIL_FROM as environment variables, or
update the constants below before running.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import resend

# ---------------------------------------------------------------------------
# Config – override via environment variables in production
# ---------------------------------------------------------------------------
RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "re_R7Dqobmv_LZzNYXVzpMJDGZ3FUeZ5qJ7y")
EMAIL_FROM      = os.getenv("EMAIL_FROM",      "onboarding@resend.dev")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Laptop Deal Alerts")

# Initialise the Resend client with the API key
resend.api_key = RESEND_API_KEY


# ---------------------------------------------------------------------------
# HTML template builder  (unchanged)
# ---------------------------------------------------------------------------

def _build_html(recommendations: List[Dict[str, Any]], recipient_name: str = "") -> str:
    """Render a clean HTML email body from the daily recommendation records."""
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi there,"
    today     = datetime.now(timezone.utc).strftime("%B %d, %Y")

    cards_html = ""
    for rec in recommendations:
        model       = rec.get("model", "N/A")
        price       = rec.get("current_price") or "N/A"
        r_score     = rec.get("r_score") or "N/A"
        cls         = rec.get("classification", "N/A")
        confidence  = rec.get("confidence", "N/A")
        explanation = rec.get("llm_explanation", "No explanation available.")

        if isinstance(price, (int, float)):
            price = f"{price:,.0f} EGP"

        cards_html += f"""
        <div style="background:#f9f9f9;border-left:4px solid #4CAF50;
                    margin:16px 0;padding:16px;border-radius:4px;">
          <p style="margin:0 0 6px 0;font-size:13px;color:#555;">
            <strong>Product:</strong>
            <a href="{model}" style="color:#1a73e8;">{model[:80]}{'…' if len(model) > 80 else ''}</a>
          </p>
          <p style="margin:0 0 6px 0;font-size:13px;color:#555;">
            <strong>Current Price:</strong> {price} &nbsp;|&nbsp;
            <strong>Score:</strong> {r_score} &nbsp;|&nbsp;
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
      These products show strong buy signals based on current pricing trends.
    </p>

    {cards_html}

    <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
    <p style="font-size:12px;color:#999;text-align:center;">
      You're receiving this because you opted in to Laptop Deal Alerts.<br>
      To unsubscribe, reply with "unsubscribe" in the subject line.
    </p>
  </div>

</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Resend dispatcher
# ---------------------------------------------------------------------------

def _send_via_resend(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """
    Send one email via the Resend SDK.
    Returns True on success, False on any error.
    """
    try:
        r = resend.Emails.send({
            "from":    f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
            "to":      to_email,
            "subject": subject,
            "html":    html_body,
        })
        # Resend returns a dict with an 'id' key on success
        if r and r.get("id"):
            return True
        print(f"  [EMAIL] Resend returned unexpected response: {r}")
        return False
    except Exception as e:
        print(f"  [EMAIL] Resend error: {e}")
        return False


# ---------------------------------------------------------------------------
# Public entry point  (signature unchanged — main_pipeline.py needs no edits)
# ---------------------------------------------------------------------------

def dispatch_laptop_alerts(
    subscribers: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
) -> Dict[str, int]:
    """
    Send today's recommendation digest to all laptop-alert subscribers.

    Parameters
    ----------
    subscribers     : list of {email, name} dicts from get_laptop_subscribers()
    recommendations : list of recommendation records from get_recommendations()

    Returns
    -------
    dict with keys 'sent' and 'failed'
    """
    if not recommendations:
        print("  [EMAIL] No recommendations to send – skipping.")
        return {"sent": 0, "failed": 0}

    if not subscribers:
        print("  [EMAIL] No active subscribers – skipping.")
        return {"sent": 0, "failed": 0}

    today   = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"🔔 Daily Laptop Deals – {today}"

    sent = failed = 0
    for sub in subscribers:
        email = sub.get("email", "")
        name  = sub.get("name",  "")
        if not email:
            continue

        html = _build_html(recommendations, recipient_name=name)
        ok   = _send_via_resend(email, name, subject, html)

        if ok:
            print(f"  [EMAIL] ✓ Sent to {email}")
            sent += 1
        else:
            print(f"  [EMAIL] ✗ Failed for {email}")
            failed += 1

    return {"sent": sent, "failed": failed}
