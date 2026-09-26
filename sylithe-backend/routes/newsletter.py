import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from db import newsletter_collection
from services.email import send_email, newsletter_email_html

logger = logging.getLogger(__name__)
newsletter_bp = Blueprint("newsletter", __name__)


@newsletter_bp.route("/newsletter", methods=["POST"])
def subscribe():
    try:
        data  = request.json
        email = data.get("email", "").strip().lower() if data else ""

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        if newsletter_collection.find_one({"email": email}):
            return jsonify({"status": "error", "message": "Already subscribed"}), 409

        newsletter_collection.insert_one({
            "email":        email,
            "subscribedAt": datetime.now(timezone.utc),
        })

        send_email(email, "Welcome to the Sylithe Newsletter!", newsletter_email_html())
        logger.info(f"New subscriber: {email}")
        return jsonify({"status": "success", "message": "Subscribed successfully"}), 201

    except Exception as e:
        logger.error(f"Newsletter error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
