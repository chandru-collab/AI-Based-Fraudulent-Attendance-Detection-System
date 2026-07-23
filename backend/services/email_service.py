"""
Email Alert Service
====================
Sends fraud alert emails using Gmail SMTP (free, no GCP needed).

Setup:
  1. Enable 2-Step Verification on your Gmail account
  2. Go to: https://myaccount.google.com/apppasswords
  3. Create an App Password (select "Mail" + "Windows Computer")
  4. Add to .env:
       SMTP_EMAIL=your.email@gmail.com
       SMTP_PASSWORD=xxxx xxxx xxxx xxxx   (the 16-char app password)
       ALERT_RECIPIENT=admin@college.edu   (who receives fraud alerts)
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import timezone, timedelta

logger = logging.getLogger("email_service")
IST = timedelta(hours=5, minutes=30)


def _to_ist(dt) -> str:
    if dt is None:
        return "—"
    try:
        utc_dt = dt.replace(tzinfo=timezone.utc)
        return utc_dt.astimezone(timezone(IST)).strftime("%d %b %Y  %I:%M %p IST")
    except Exception:
        return str(dt)


def send_fraud_alert(username: str, risk_score: float, timestamp, rules_triggered: list):
    """Send an email alert when attendance is flagged as fraud."""
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    recipient = os.getenv("ALERT_RECIPIENT", smtp_email).strip()

    if not smtp_email or not smtp_password:
        logger.warning("Email alerts disabled: SMTP_EMAIL / SMTP_PASSWORD not set in .env")
        return False

    try:
        subject = f"⚠️ Fraud Alert: {username} flagged ({risk_score:.0f}% risk)"

        rules_html = "".join(
            f"<li style='margin:4px 0;color:#dc2626;'>🚨 {r}</li>" for r in rules_triggered
        ) or "<li>General anomaly detected</li>"

        html_body = f"""
        <div style="font-family:sans-serif;max-width:560px;margin:auto;background:#0f172a;color:#e2e8f0;padding:28px;border-radius:12px;border:1px solid #1e293b;">
          <h2 style="color:#f43f5e;margin-top:0;">⚠️ Attendance Fraud Alert</h2>
          <p style="color:#94a3b8;font-size:14px;">The AI fraud detection system has flagged a suspicious attendance attempt.</p>

          <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
            <tr><td style="padding:8px;color:#64748b;width:40%;">Student</td>
                <td style="padding:8px;color:#f1f5f9;font-weight:bold;">{username}</td></tr>
            <tr style="background:#1e293b;"><td style="padding:8px;color:#64748b;">Risk Score</td>
                <td style="padding:8px;color:#f43f5e;font-weight:bold;">{risk_score:.0f}%</td></tr>
            <tr><td style="padding:8px;color:#64748b;">Timestamp</td>
                <td style="padding:8px;color:#f1f5f9;">{_to_ist(timestamp)}</td></tr>
            <tr style="background:#1e293b;"><td style="padding:8px;color:#64748b;">Status</td>
                <td style="padding:8px;color:#f43f5e;font-weight:bold;">FLAGGED</td></tr>
          </table>

          <div style="background:#1e293b;border-radius:8px;padding:14px;margin-top:12px;">
            <p style="margin:0 0 8px;color:#94a3b8;font-size:13px;font-weight:bold;">Rules Triggered:</p>
            <ul style="margin:0;padding-left:18px;">{rules_html}</ul>
          </div>

          <p style="margin-top:20px;font-size:12px;color:#475569;">
            Review this record in the <strong>Admin Dashboard → Fraud Logs</strong> tab.
          </p>
          <hr style="border:none;border-top:1px solid #1e293b;margin:16px 0;">
          <p style="font-size:11px;color:#334155;text-align:center;">AI Attendance System — Auto-generated alert</p>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_email
        msg["To"] = recipient
        msg.attach(MIMEText(html_body, "html"))

        # Dummy fallback: If password is not 16 chars (App Password) or if SMTP fails
        is_dummy = len(smtp_password.replace(" ", "")) != 16
        
        if is_dummy:
            logger.info("Using DUMMY EMAIL MODE. Saving email to disk.")
            with open("backend/uploads/last_fraud_alert.html", "w", encoding="utf-8") as f:
                f.write(html_body)
            logger.info(f"Dummy alert saved for {username} to backend/uploads/last_fraud_alert.html")
            return True

        # Real SMTP attempt
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, recipient, msg.as_string())

        logger.info(f"Fraud alert email sent for {username} (risk={risk_score:.0f}%)")
        return True

    except Exception as e:
        logger.error(f"Failed to send fraud alert email (or connect to SMTP): {e}")
        # Fallback to local save even on error
        with open("backend/uploads/last_fraud_alert.html", "w", encoding="utf-8") as f:
            f.write(html_body)
        logger.info("Saved alert to backend/uploads/last_fraud_alert.html as fallback.")
        return False
