import logging
from datetime import datetime
from threading import Thread
import resend
from config import RESEND_API_KEY, FROM_ADDRESS

logger = logging.getLogger(__name__)

resend.api_key = RESEND_API_KEY


def _send(to_email: str, subject: str, html: str):
    if not RESEND_API_KEY:
        logger.error(f"Email skipped for {to_email}: RESEND_API_KEY is not set")
        return
    try:
        result = resend.Emails.send({
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent to {to_email} — id {result.get('id')}")
    except Exception as e:
        logger.error(f"Email failed for {to_email}: {e}")


def send_email(to_email: str, subject: str, html: str):
    """Fire-and-forget email — does not block the request."""
    Thread(target=_send, args=(to_email, subject, html), daemon=True).start()


# ==================== EMAIL TEMPLATES ====================

def otp_email_html(name: str, otp: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#F1F1F1;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F1F1F1;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#fff;border-radius:16px;overflow:hidden;">
        <tr><td style="background-color:#08292F;padding:40px;text-align:center;">
          <h1 style="color:#fff;font-size:28px;margin:0 0 8px 0;">Sylithe</h1>
          <p style="color:#A3E635;font-size:14px;margin:0;letter-spacing:2px;text-transform:uppercase;">Carbon Intelligence Platform</p>
        </td></tr>
        <tr><td style="padding:40px 40px 20px;">
          <h2 style="color:#0F172A;font-size:22px;margin:0 0 12px;">Hi {name}, verify your email</h2>
          <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 28px;">Use the one-time code below to verify your email address. This code expires in <strong>10 minutes</strong>.</p>
          <div style="background-color:#F0FDF4;border:2px solid #A3E635;border-radius:12px;padding:28px;text-align:center;margin-bottom:28px;">
            <p style="color:#64748B;font-size:13px;letter-spacing:2px;text-transform:uppercase;margin:0 0 10px;">Your verification code</p>
            <p style="color:#08292F;font-size:40px;font-weight:900;letter-spacing:10px;margin:0;font-family:monospace;">{otp}</p>
          </div>
          <p style="color:#94A3B8;font-size:13px;line-height:1.6;margin:0;">If you didn't request this code, you can safely ignore this email. Do not share this code with anyone.</p>
        </td></tr>
        <tr><td style="padding:0 40px;"><div style="border-top:1px solid #E2E8F0;"></div></td></tr>
        <tr><td style="padding:24px 40px 32px;text-align:center;">
          <p style="color:#94A3B8;font-size:13px;margin:0 0 8px;">Questions? <a href="mailto:info@sylithe.com" style="color:#16a34a;text-decoration:none;">info@sylithe.com</a></p>
          <p style="color:#CBD5E1;font-size:12px;margin:0;">&copy; {datetime.now().year} Sylithe. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def welcome_email_html(name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#F1F1F1;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F1F1F1;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#fff;border-radius:16px;overflow:hidden;">
        <tr><td style="background-color:#08292F;padding:40px;text-align:center;">
          <h1 style="color:#fff;font-size:28px;margin:0 0 8px 0;">Sylithe</h1>
          <p style="color:#A3E635;font-size:14px;margin:0;letter-spacing:2px;text-transform:uppercase;">Carbon Intelligence Platform</p>
        </td></tr>
        <tr><td style="padding:40px 40px 20px;">
          <h2 style="color:#0F172A;font-size:24px;margin:0 0 16px;">Welcome aboard, {name}!</h2>
          <p style="color:#475569;font-size:16px;line-height:1.7;">Thank you for signing up with Sylithe. We've received your request and we're excited to have you join us on the journey toward confident, science-backed climate action.</p>
        </td></tr>
        <tr><td style="padding:0 40px 20px;">
          <table width="100%" style="background-color:#F8FAFC;border-radius:12px;border:1px solid #E2E8F0;">
            <tr><td style="padding:24px;">
              <h3 style="color:#0F172A;font-size:18px;margin:0 0 16px;">What happens next?</h3>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 12px;"><strong style="color:#0F172A;">1. Account review</strong><br>Our team will review your details and verify your account within 24–48 hours.</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 12px;"><strong style="color:#0F172A;">2. Personalized walkthrough</strong><br>A member of our team will reach out to schedule a demo tailored to your needs.</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0;"><strong style="color:#0F172A;">3. Platform access</strong><br>Once verified, you'll get full access to Sylithe's carbon intelligence tools.</p>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:10px 40px 30px;text-align:center;">
          <a href="https://sylithe.com" style="display:inline-block;background-color:#08292F;color:#fff;text-decoration:none;padding:14px 32px;border-radius:50px;font-size:14px;font-weight:bold;">Visit Sylithe</a>
        </td></tr>
        <tr><td style="padding:0 40px;"><div style="border-top:1px solid #E2E8F0;"></div></td></tr>
        <tr><td style="padding:24px 40px 32px;text-align:center;">
          <p style="color:#94A3B8;font-size:13px;margin:0 0 8px;">Questions? Reach us at <a href="mailto:info@sylithe.com" style="color:#16a34a;text-decoration:none;">info@sylithe.com</a></p>
          <p style="color:#CBD5E1;font-size:12px;margin:0;">&copy; {datetime.now().year} Sylithe. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def free_tier_welcome_email_html(name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#F1F1F1;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F1F1F1;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#fff;border-radius:16px;overflow:hidden;">
        <tr><td style="background-color:#08292F;padding:40px;text-align:center;">
          <h1 style="color:#fff;font-size:28px;margin:0 0 8px 0;">Sylithe</h1>
          <p style="color:#A3E635;font-size:14px;margin:0;letter-spacing:2px;text-transform:uppercase;">Carbon Intelligence Platform</p>
        </td></tr>
        <tr><td style="padding:40px 40px 20px;">
          <h2 style="color:#0F172A;font-size:24px;margin:0 0 16px;">Welcome to Sylithe, {name}!</h2>
          <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 20px;">
            Your account has been created and you now have <strong style="color:#08292F;">Free Tier access</strong> to the Sylithe platform. Here's what you can explore right now:
          </p>
        </td></tr>
        <tr><td style="padding:0 40px 20px;">
          <table width="100%" style="background-color:#F0FDF4;border-radius:12px;border:1px solid #bbf7d0;">
            <tr><td style="padding:24px;">
              <h3 style="color:#15803d;font-size:16px;margin:0 0 14px;">&#10003; Free Tier Includes</h3>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px;">&#9679; &nbsp;<strong>Project Registry</strong> — Browse the first 5 Verra VCS and Gold Standard India projects</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0;">&#9679; &nbsp;<strong>Project Profiles</strong> — View basic project information, status and registry details</p>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:0 40px 20px;">
          <table width="100%" style="background-color:#FFF7ED;border-radius:12px;border:1px solid #fed7aa;">
            <tr><td style="padding:24px;">
              <h3 style="color:#c2410c;font-size:16px;margin:0 0 14px;">&#128274; Upgrade to Pro for Full Access</h3>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px;">&#9679; &nbsp;Full Project Registry (1,000+ India projects across all registries)</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px;">&#9679; &nbsp;Dashboard with live carbon portfolio analytics</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px;">&#9679; &nbsp;Canopy Height Model (CHM) &amp; LULC satellite analysis</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px;">&#9679; &nbsp;Above Ground Biomass (AGB) estimation</p>
              <p style="color:#475569;font-size:14px;line-height:1.6;margin:0;">&#9679; &nbsp;Automated MRV reports &amp; PDF export</p>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:0 40px 30px;">
          <p style="color:#0F172A;font-size:15px;line-height:1.7;margin:0 0 20px;">
            To upgrade to Pro and unlock the full platform, simply reply to this email or reach out to our team directly.
          </p>
          <table cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding-right:16px;">
                <a href="mailto:info@sylithe.com?subject=Upgrade to Pro - {name}" style="display:inline-block;background-color:#08292F;color:#fff;text-decoration:none;padding:14px 28px;border-radius:50px;font-size:14px;font-weight:bold;">Contact Team for Upgrade</a>
              </td>
              <td>
                <a href="https://sylithe.com/projects" style="display:inline-block;background-color:#F0FDF4;color:#15803d;border:1px solid #A3E635;text-decoration:none;padding:14px 28px;border-radius:50px;font-size:14px;font-weight:bold;">Explore Free Registry</a>
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:0 40px;"><div style="border-top:1px solid #E2E8F0;"></div></td></tr>
        <tr><td style="padding:24px 40px 32px;text-align:center;">
          <p style="color:#94A3B8;font-size:13px;margin:0 0 8px;">Questions? <a href="mailto:info@sylithe.com" style="color:#16a34a;text-decoration:none;">info@sylithe.com</a> &nbsp;|&nbsp; +91 7774870242</p>
          <p style="color:#CBD5E1;font-size:12px;margin:0;">&copy; {datetime.now().year} Sylithe. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def password_reset_email_html(name: str, otp: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#F1F1F1;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F1F1F1;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#fff;border-radius:16px;overflow:hidden;">
        <tr><td style="background-color:#08292F;padding:40px;text-align:center;">
          <h1 style="color:#fff;font-size:28px;margin:0 0 8px 0;">Sylithe</h1>
          <p style="color:#A3E635;font-size:14px;margin:0;letter-spacing:2px;text-transform:uppercase;">Carbon Intelligence Platform</p>
        </td></tr>
        <tr><td style="padding:40px 40px 20px;">
          <h2 style="color:#0F172A;font-size:22px;margin:0 0 12px;">Password Reset Request</h2>
          <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 28px;">Hi {name}, use the code below to reset your password. This code expires in <strong>10 minutes</strong>.</p>
          <div style="background-color:#FFF7ED;border:2px solid #fed7aa;border-radius:12px;padding:28px;text-align:center;margin-bottom:28px;">
            <p style="color:#64748B;font-size:13px;letter-spacing:2px;text-transform:uppercase;margin:0 0 10px;">Your reset code</p>
            <p style="color:#08292F;font-size:40px;font-weight:900;letter-spacing:10px;margin:0;font-family:monospace;">{otp}</p>
          </div>
          <p style="color:#94A3B8;font-size:13px;line-height:1.6;margin:0;">If you didn't request a password reset, you can safely ignore this email.</p>
        </td></tr>
        <tr><td style="padding:0 40px;"><div style="border-top:1px solid #E2E8F0;"></div></td></tr>
        <tr><td style="padding:24px 40px 32px;text-align:center;">
          <p style="color:#94A3B8;font-size:13px;margin:0 0 8px;">Questions? <a href="mailto:info@sylithe.com" style="color:#16a34a;text-decoration:none;">info@sylithe.com</a></p>
          <p style="color:#CBD5E1;font-size:12px;margin:0;">&copy; {datetime.now().year} Sylithe. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def newsletter_email_html() -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#F1F1F1;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F1F1F1;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#fff;border-radius:16px;overflow:hidden;">
        <tr><td style="background-color:#08292F;padding:40px;text-align:center;">
          <h1 style="color:#fff;font-size:28px;margin:0 0 8px 0;">Sylithe</h1>
          <p style="color:#A3E635;font-size:14px;margin:0;letter-spacing:2px;text-transform:uppercase;">Carbon Intelligence Platform</p>
        </td></tr>
        <tr><td style="padding:40px;">
          <h2 style="color:#0F172A;font-size:24px;margin:0 0 16px;">You're on the list!</h2>
          <p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 20px;">Thank you for subscribing to the Sylithe newsletter. You'll be the first to know about:</p>
          <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
            <tr><td style="padding:6px 0;color:#475569;font-size:14px;"><span style="color:#16a34a;font-weight:bold;margin-right:8px;">&#9679;</span> New platform features and product updates</td></tr>
            <tr><td style="padding:6px 0;color:#475569;font-size:14px;"><span style="color:#16a34a;font-weight:bold;margin-right:8px;">&#9679;</span> Carbon market insights and research</td></tr>
            <tr><td style="padding:6px 0;color:#475569;font-size:14px;"><span style="color:#16a34a;font-weight:bold;margin-right:8px;">&#9679;</span> Methodology deep-dives and case studies</td></tr>
            <tr><td style="padding:6px 0;color:#475569;font-size:14px;"><span style="color:#16a34a;font-weight:bold;margin-right:8px;">&#9679;</span> Exclusive early access and offers</td></tr>
          </table>
          <p style="color:#475569;font-size:14px;line-height:1.6;">We respect your inbox — expect only meaningful updates, no spam.</p>
        </td></tr>
        <tr><td style="padding:0 40px 30px;text-align:center;">
          <a href="https://sylithe.com" style="display:inline-block;background-color:#08292F;color:#fff;text-decoration:none;padding:14px 32px;border-radius:50px;font-size:14px;font-weight:bold;">Explore Sylithe</a>
        </td></tr>
        <tr><td style="padding:0 40px;"><div style="border-top:1px solid #E2E8F0;"></div></td></tr>
        <tr><td style="padding:24px 40px 32px;text-align:center;">
          <p style="color:#94A3B8;font-size:13px;margin:0 0 8px;">Questions? Reach us at <a href="mailto:info@sylithe.com" style="color:#16a34a;text-decoration:none;">info@sylithe.com</a></p>
          <p style="color:#CBD5E1;font-size:12px;margin:0;">&copy; {datetime.now().year} Sylithe. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
