from pymongo import MongoClient, ASCENDING
from config import MONGO_URI

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set. Please create a .env file with your MongoDB connection string.")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["sylithe"]

users_collection              = db["users"]
newsletter_collection         = db["newsletter"]
projects_collection           = db["projects_cache"]
otp_collection                = db["otp_tokens"]
free_scans_collection         = db["free_scans"]
access_requests_collection    = db["access_requests"]
developer_projects_collection = db["developer_projects"]
dev_activity_collection       = db["dev_activity"]
tree_inventory_collection     = db["tree_inventory"]
lulc_reports_collection       = db["lulc_reports"]
feature_usage_collection      = db["feature_usage"]

# --- Sylverra: Module 1 (company intelligence), Module 2 (project ratings), agent layer ---
companies_collection          = db["companies"]
company_documents_collection  = db["company_documents"]
company_metrics_collection    = db["company_metrics"]
company_ratings_collection    = db["company_ratings"]
project_documents_collection  = db["project_documents"]
project_ratings_collection    = db["project_ratings"]
rating_reviews_collection     = db["rating_reviews"]
evidence_collection           = db["evidence"]
jobs_collection               = db["jobs"]
agent_runs_collection         = db["agent_runs"]
ai_cache_collection           = db["ai_cache"]
calc_inventories_collection   = db["calc_inventories"]
calc_uploads_collection       = db["calc_uploads"]
research_sessions_collection  = db["research_sessions"]
nse_equities_collection       = db["nse_equities"]
registry_projects_collection  = db["registry_projects"]
registry_meta_collection      = db["registry_meta"]
document_text_cache_collection = db["document_text_cache"]
sbti_companies_collection     = db["sbti_companies"]
sbti_targets_collection       = db["sbti_targets"]

try:
    users_collection.create_index([("email", ASCENDING)], unique=True)
    otp_collection.create_index([("email", ASCENDING)])
    projects_collection.create_index([("country", ASCENDING), ("cached_at", ASCENDING)])
    projects_collection.create_index([("country", ASCENDING), ("registry", ASCENDING)])
    projects_collection.create_index([("country", ASCENDING), ("state", ASCENDING)])
    projects_collection.create_index([("country", ASCENDING), ("status", ASCENDING)])
    projects_collection.create_index([("country", ASCENDING), ("credits_issued", ASCENDING)])
    projects_collection.create_index([("name", ASCENDING)])
    free_scans_collection.create_index([("email", ASCENDING), ("created_at", ASCENDING)])
    access_requests_collection.create_index([("user_email", ASCENDING)])
    access_requests_collection.create_index([("status", ASCENDING)])
    access_requests_collection.create_index([("requested_at", ASCENDING)])
    developer_projects_collection.create_index([("developer_email", ASCENDING), ("created_at", ASCENDING)])
    dev_activity_collection.create_index([("developer_email", ASCENDING), ("timestamp", ASCENDING)])
    tree_inventory_collection.create_index([("developer_email", ASCENDING), ("project_id", ASCENDING), ("plot_index", ASCENDING)])
    lulc_reports_collection.create_index([("email", ASCENDING), ("created_at", ASCENDING)])
    feature_usage_collection.create_index([("email", ASCENDING), ("action", ASCENDING)])
    companies_collection.create_index([("slug", ASCENDING)], unique=True)
    companies_collection.create_index([("name", "text"), ("aliases", "text"), ("industry", "text")])
    company_documents_collection.create_index([("company_id", ASCENDING), ("document_type", ASCENDING)])
    company_documents_collection.create_index([("company_id", ASCENDING), ("source_url", ASCENDING)], unique=True)
    company_metrics_collection.create_index([("company_id", ASCENDING), ("metric", ASCENDING), ("period", ASCENDING)])
    company_ratings_collection.create_index([("company_id", ASCENDING), ("created_at", ASCENDING)])
    project_documents_collection.create_index([("project_id", ASCENDING)])
    project_ratings_collection.create_index([("project_id", ASCENDING), ("created_at", ASCENDING)])
    rating_reviews_collection.create_index([("rating_id", ASCENDING)])
    evidence_collection.create_index([("subject_type", ASCENDING), ("subject_id", ASCENDING)])
    evidence_collection.create_index([("evidence_id", ASCENDING)], unique=True)
    jobs_collection.create_index([("subject_type", ASCENDING), ("subject_id", ASCENDING), ("created_at", ASCENDING)])
    # at most one running job per (kind, subject) — prevents duplicate agent runs from double clicks
    jobs_collection.create_index([("kind", ASCENDING), ("subject_type", ASCENDING), ("subject_id", ASCENDING)],
                                 unique=True, partialFilterExpression={"status": "running"}, name="one_running_job")
    agent_runs_collection.create_index([("created_at", ASCENDING)])
    calc_inventories_collection.create_index([("owner_email", ASCENDING)])
    calc_uploads_collection.create_index([("inventory_id", ASCENDING)])
    registry_projects_collection.create_index([("country", ASCENDING), ("registry", ASCENDING)])
    registry_projects_collection.create_index([("category", ASCENDING)])
    registry_projects_collection.create_index([("issued", ASCENDING)])
    registry_projects_collection.create_index([("proponent", ASCENDING)])
    registry_projects_collection.create_index([("name", "text"), ("proponent", "text"), ("project_id", "text")])
    sbti_companies_collection.create_index([("isin", ASCENDING)])
    sbti_companies_collection.create_index([("name_norm", ASCENDING)])
    sbti_targets_collection.create_index([("sbti_id", ASCENDING)])
    research_sessions_collection.create_index([("owner_email", ASCENDING), ("updated_at", ASCENDING)])
except Exception as e:
    print(f"Warning: Could not create indexes: {e}")
