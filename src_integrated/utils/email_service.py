import os
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src_integrated.database.models import DailyRecommendation, PriceHistory, Product, Subscriber

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_R7Dqobmv_LZzNYXVzpMJDGZ3FUeZ5qJ7y")
EMAIL_FROM       = os.getenv("EMAIL_FROM",       "onboarding@resend.dev") # Resend test email
EMAIL_FROM_NAME  = os.getenv("EMAIL_FROM_NAME",  "Wise Purchaser")
RESEND_URL       = "https://api.resend.com/emails"

def _build_html(recommendations: List[Dict[str, Any]], recipient_name: str = "") -> str:
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi there,"
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    
    cards_html = ""
    for rec in recommendations:
        model = rec.get("model", "N/A")
        price = rec.get("current_price", "N/A")
        score = rec.get("intelligent_score", "N/A")
        path = rec.get("routing_path", "N/A")
        justification = rec.get("justification", "No explanation available.")
        
        if isinstance(price, (int, float)):
            price = f"{price:,.0f} EGP"
        if isinstance(score, (int, float)):
            score = f"{score:.2f}"
            
        cards_html += f"""
        <div style="background:#161b22;border-left:4px solid #00ffcc;
                    margin:16px 0;padding:16px;border-radius:4px;">
          <p style="margin:0 0 6px 0;font-size:13px;color:#c9d1d9;">
            <strong style="color:#fff;">Product:</strong>
            <span style="color:#00b4ff;">{model}</span>
          </p>
          <p style="margin:0 0 6px 0;font-size:13px;color:#c9d1d9;">
            <strong style="color:#fff;">Current Price:</strong> {price} &nbsp;|&nbsp;
            <strong style="color:#fff;">Intelligent Score:</strong> {score} &nbsp;|&nbsp;
            <strong style="color:#fff;">Routing Path:</strong> {path}
          </p>
          <p style="margin:0;font-size:14px;color:#c9d1d9;line-height:1.6;">
            {justification}
          </p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily Laptop Deals – {today}</title></head>
<body style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:20px;color:#c9d1d9;background:#0d1117;">

  <div style="background:linear-gradient(90deg, #00ffcc, #00b4ff);padding:20px;border-radius:6px 6px 0 0;text-align:center;">
    <h1 style="color:#0d1117;margin:0;font-size:22px;">🔔 Daily Laptop Deal Alert</h1>
    <p style="color:#0d1117;margin:6px 0 0 0;font-size:13px;font-weight:bold;">{today} · Autonomous Recommendation Engine</p>
  </div>

  <div style="background:#161b22;padding:24px;border:1px solid #30363d;border-top:none;border-radius:0 0 6px 6px;">
    <p style="font-size:15px;color:#fff;">{greeting}</p>
    <p style="font-size:14px;color:#c9d1d9;">
      Here are today's top laptop deals identified by the Wise Purchaser B2C pipeline.
      These products have been verified by the ReAct Agentic Router.
    </p>

    {cards_html}

    <hr style="border:none;border-top:1px solid #30363d;margin:24px 0;">
    <p style="font-size:12px;color:#8b949e;text-align:center;">
      You're receiving this because you opted in to Laptop Deal Alerts.<br>
      To unsubscribe, reply with "unsubscribe" in the subject line.
    </p>
  </div>
</body>
</html>"""
    return html

def _send_via_email_provider(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    payload = {
        "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
        "to": [f"{to_name} <{to_email}>"] if to_name else [to_email],
        "subject": subject,
        "html": html_body
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type":  "application/json",
    }
    try:
        resp = requests.post(RESEND_URL, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201, 202):
            return True
        print(f"  [EMAIL] Resend returned {resp.status_code}: {resp.text[:200]}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  [EMAIL] Request failed: {e}")
        return False
def dispatch_b2c_emails(db: Session):
    """
    Event-driven service: Queries daily_recommendations for Approved and emailed=False,
    dispatches emails, and updates the emailed boolean.
    """
    pending_recs = db.query(DailyRecommendation, PriceHistory, Product).join(
        PriceHistory, DailyRecommendation.price_history_id == PriceHistory.id
    ).join(
        Product, PriceHistory.product_id == Product.id
    ).filter(
        DailyRecommendation.status == "Approved",
        DailyRecommendation.emailed == False
    ).all()

    if not pending_recs:
        print("  [EMAIL] No pending approved recommendations to send.")
        return {"sent": 0, "failed": 0, "recs_processed": 0}
        
    subscribers = db.query(Subscriber).filter(Subscriber.active == True, Subscriber.category == 'laptop').all()
    if not subscribers:
        print("  [EMAIL] No active subscribers. Marking records as emailed anyway to prevent backlog.")
        for rec, _, _ in pending_recs:
            rec.emailed = True
        db.commit()
        return {"sent": 0, "failed": 0, "recs_processed": len(pending_recs)}

    recs_data = []
    for rec, ph, p in pending_recs:
        recs_data.append({
            "model": p.raw_title,
            "current_price": ph.raw_current_price,
            "intelligent_score": rec.intelligent_score,
            "routing_path": rec.routing_path,
            "justification": rec.justification
        })

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"🔔 Daily Laptop Deals – {today}"

    sent = 0
    failed = 0
    
    for sub in subscribers:
        email = sub.email
        name = sub.name or ""
        
        html = _build_html(recs_data, recipient_name=name)
        ok = _send_via_email_provider(email, name, subject, html)
        
        if ok:
            sent += 1
            print(f"  [EMAIL] ✓ Sent to {email}")
        else:
            failed += 1
            print(f"  [EMAIL] ✗ Failed for {email}")

    for rec, _, _ in pending_recs:
        rec.emailed = True
    
    db.commit()
    return {"sent": sent, "failed": failed, "recs_processed": len(pending_recs)}
