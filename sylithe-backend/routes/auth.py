import logging
import random
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
import requests as http_requests
from flask import Blueprint, jsonify, request

from config import JWT_SECRET, JWT_EXPIRY_DAYS, HCAPTCHA_SECRET
from db import users_collection, otp_collection
from services.email import send_email, otp_email_html, free_tier_welcome_email_html, password_reset_email_html
from utils.auth import require_auth

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_me():
    user = users_collection.find_one({"email": request.current_user["email"]})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    return jsonify({
        "status": "success",
        "user": {
            "fullName":        user["fullName"],
            "email":           user["email"],
            "tier":            user.get("tier", "free"),
            "primaryActivity": user.get("primaryActivity", ""),
        },
    }), 200


def _verify_hcaptcha(token: str) -> bool:
    try:
        resp = http_requests.post(
            "https://api.hcaptcha.com/siteverify",
            data={"secret": HCAPTCHA_SECRET, "response": token},
            timeout=5,
        )
        return resp.json().get("success", False)
    except Exception:
        return False


@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    try:
        data = request.json
        email          = (data.get("email")           or "").strip().lower()
        name           = (data.get("name")            or "User").strip()
        captcha_token  = (data.get("captchaToken")    or "").strip()

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        if not captcha_token or not _verify_hcaptcha(captcha_token):
            return jsonify({"status": "error", "message": "Captcha verification failed. Please try again."}), 400

        if users_collection.find_one({"email": email}):
            return jsonify({"status": "error", "message": "Email already registered"}), 409

        otp = str(random.randint(100000, 999999))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        otp_collection.update_one(
            {"email": email},
            {"$set": {"otp": otp, "expires_at": expires_at, "verified": False, "attempts": 0}},
            upsert=True,
        )

        send_email(email, "Your Sylithe Verification Code", otp_email_html(name, otp))
        logger.info(f"OTP sent to {email}")
        return jsonify({"status": "success", "message": "OTP sent to your email"}), 200

    except Exception as e:
        logger.error(f"Send OTP error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    try:
        data = request.json
        email = (data.get("email") or "").strip().lower()
        otp   = (data.get("otp")   or "").strip()

        if not email or not otp:
            return jsonify({"status": "error", "message": "Email and OTP are required"}), 400

        record = otp_collection.find_one({"email": email})
        if not record:
            return jsonify({"status": "error", "message": "No OTP found. Please request a new one."}), 404

        if record.get("attempts", 0) >= 5:
            return jsonify({"status": "error", "message": "Too many attempts. Please request a new OTP."}), 429

        if datetime.now(timezone.utc) > record["expires_at"].replace(tzinfo=timezone.utc):
            return jsonify({"status": "error", "message": "OTP has expired. Please request a new one."}), 410

        otp_collection.update_one({"email": email}, {"$inc": {"attempts": 1}})

        if record["otp"] != otp:
            remaining = 4 - record.get("attempts", 0)
            return jsonify({"status": "error", "message": f"Incorrect OTP. {remaining} attempt(s) remaining."}), 400

        otp_collection.update_one({"email": email}, {"$set": {"verified": True}})
        logger.info(f"OTP verified for {email}")
        return jsonify({"status": "success", "message": "Email verified successfully"}), 200

    except Exception as e:
        logger.error(f"Verify OTP error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        required = ["fullName", "email", "mobile", "password"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

        if len(data["password"]) < 8:
            return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400

        email = data["email"].strip().lower()

        if users_collection.find_one({"email": email}):
            return jsonify({"status": "error", "message": "Email already registered"}), 409

        otp_record = otp_collection.find_one({"email": email})
        if not otp_record or not otp_record.get("verified"):
            return jsonify({"status": "error", "message": "Email not verified. Please complete OTP verification."}), 403

        hashed_pw = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        users_collection.insert_one({
            "fullName":        data.get("fullName"),
            "email":           email,
            "mobile":          data.get("mobile"),
            "password":        hashed_pw,
            "companyName":     data.get("companyName", ""),
            "designation":     data.get("designation", ""),
            "primaryActivity": data.get("primaryActivity", ""),
            "projectType":     data.get("projectType", ""),
            "companySize":     data.get("companySize", ""),
            "interestArea":    data.get("interestArea", ""),
            "hearAbout":       data.get("hearAbout", ""),
            "tier":            "free",
            "created_at":      datetime.now(timezone.utc),
        })

        otp_collection.delete_one({"email": email})

        send_email(
            email,
            "Welcome to Sylithe — Your Free Access is Ready!",
            free_tier_welcome_email_html(data["fullName"]),
        )
        logger.info(f"New signup: {email}")
        return jsonify({"status": "success", "message": "Account created successfully"}), 201

    except Exception as e:
        logger.error(f"Signup error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    try:
        data = request.json
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"status": "error", "message": "No account found with this email"}), 404

        otp = str(random.randint(100000, 999999))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        otp_collection.update_one(
            {"email": email},
            {"$set": {"otp": otp, "expires_at": expires_at, "verified": False, "attempts": 0, "purpose": "reset"}},
            upsert=True,
        )

        send_email(email, "Reset Your Sylithe Password", password_reset_email_html(user["fullName"], otp))
        logger.info(f"Password reset OTP sent to {email}")
        return jsonify({"status": "success", "message": "Reset code sent to your email"}), 200

    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route("/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    try:
        data  = request.json
        email = (data.get("email") or "").strip().lower()
        otp   = (data.get("otp")   or "").strip()

        if not email or not otp:
            return jsonify({"status": "error", "message": "Email and OTP are required"}), 400

        record = otp_collection.find_one({"email": email})
        if not record or record.get("purpose") != "reset":
            return jsonify({"status": "error", "message": "No reset request found. Please request a new code."}), 404

        if record.get("attempts", 0) >= 5:
            return jsonify({"status": "error", "message": "Too many attempts. Please request a new code."}), 429

        if datetime.now(timezone.utc) > record["expires_at"].replace(tzinfo=timezone.utc):
            return jsonify({"status": "error", "message": "Code has expired. Please request a new one."}), 410

        otp_collection.update_one({"email": email}, {"$inc": {"attempts": 1}})

        if record["otp"] != otp:
            remaining = 4 - record.get("attempts", 0)
            return jsonify({"status": "error", "message": f"Incorrect code. {remaining} attempt(s) remaining."}), 400

        otp_collection.update_one({"email": email}, {"$set": {"verified": True}})
        logger.info(f"Reset OTP verified for {email}")
        return jsonify({"status": "success", "message": "Code verified"}), 200

    except Exception as e:
        logger.error(f"Verify reset OTP error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    try:
        data     = request.json
        email    = (data.get("email")    or "").strip().lower()
        password = (data.get("password") or "")

        if not email or not password:
            return jsonify({"status": "error", "message": "Email and new password are required"}), 400

        if len(password) < 8:
            return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400

        record = otp_collection.find_one({"email": email})
        if not record or record.get("purpose") != "reset" or not record.get("verified"):
            return jsonify({"status": "error", "message": "OTP not verified. Please restart the reset flow."}), 403

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        users_collection.update_one({"email": email}, {"$set": {"password": hashed_pw}})
        otp_collection.delete_one({"email": email})

        logger.info(f"Password reset successful for {email}")
        return jsonify({"status": "success", "message": "Password reset successfully"}), 200

    except Exception as e:
        logger.error(f"Reset password error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        email    = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"status": "error", "message": "Email and password are required"}), 400

        user = users_collection.find_one({"email": email})
        if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401

        tier  = user.get("tier", "free")
        token = jwt.encode(
            {
                "user_id": str(user["_id"]),
                "email":   user["email"],
                "tier":    tier,
                "exp":     datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
            },
            JWT_SECRET,
            algorithm="HS256",
        )

        logger.info(f"Login: {user['email']} (tier={tier})")
        return jsonify({
            "status": "success",
            "token":  token,
            "user": {
                "fullName":        user["fullName"],
                "email":           user["email"],
                "tier":            tier,
                "primaryActivity": user.get("primaryActivity", ""),
            },
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
