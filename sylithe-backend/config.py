import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
HCAPTCHA_SECRET = os.environ.get("HCAPTCHA_SECRET", "")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set. Configure it in the backend environment.")

FROM_EMAIL = "info@sylithe.com"
# Resend "from" field — display name + verified domain address
FROM_ADDRESS = f"Sylithe <{FROM_EMAIL}>"
JWT_EXPIRY_DAYS = 7
# Default platform admins (always granted), plus any set via the ADMIN_EMAILS env var.
_DEFAULT_ADMIN_EMAILS = {"karan270905@gmail.com", "chhelurathore773@gmail.com"}
ADMIN_EMAILS = _DEFAULT_ADMIN_EMAILS | set(
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
)
# Users with unlimited usage (LULC reports, CHM, all gated features) — not admin access.
UNLIMITED_EMAILS = {"karan270905@gmail.com", "sagarpatidar20052005@gmail.com"} | ADMIN_EMAILS
CACHE_TTL_HOURS = 24

CORS_ORIGINS = [
    "https://sylithe-frontend.vercel.app",
    "https://sylithe.com",
    "https://www.sylithe.com",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5176",
    "http://localhost:5177",
]

REGISTRY_COLORS = {
    "Verra VCS": "#2563eb",
    "Gold Standard": "#d97706",
    "ACR": "#ea580c",
    "CAR": "#7c3aed",
    "Plan Vivo": "#16a34a",
}
