import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS

from config import CORS_ORIGINS
from routes.auth import auth_bp
from routes.newsletter import newsletter_bp
from routes.projects import projects_bp
from routes.analytics import analytics_bp
from routes.chm import chm_bp
from routes.free_tier import free_tier_bp
from routes.admin import admin_bp
from routes.developer_projects import dev_projects_bp
from routes.tree_inventory import tree_inv_bp
from routes.reports import reports_bp
from routes.companies import companies_bp
from routes.project_intel import intel_bp
from routes.calculator import calculator_bp
from routes.research import research_bp

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 21 * 1024 * 1024  # calculator uploads (20 MB) + form overhead
CORS(app, origins=CORS_ORIGINS)

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(newsletter_bp, url_prefix='/api')
app.register_blueprint(projects_bp, url_prefix='/api')
app.register_blueprint(analytics_bp, url_prefix='/api/gee')
app.register_blueprint(chm_bp, url_prefix='/api/chm')
app.register_blueprint(free_tier_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api')
app.register_blueprint(dev_projects_bp, url_prefix='/api')
app.register_blueprint(tree_inv_bp, url_prefix='/api')
app.register_blueprint(reports_bp, url_prefix='/api')
# Sylithe — Module 1 (company intelligence), Module 2 (project ratings), calculator, research agent
app.register_blueprint(companies_bp, url_prefix='/api')
app.register_blueprint(intel_bp, url_prefix='/api')
app.register_blueprint(calculator_bp, url_prefix='/api')
app.register_blueprint(research_bp, url_prefix='/api')


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=debug)
