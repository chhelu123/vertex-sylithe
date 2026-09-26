import pymongo
from config import MONGO_URI

client = pymongo.MongoClient(MONGO_URI)
db = client["sylithe"]
print("All registries:", db.projects_cache.distinct("registry"))
print("All countries:", db.projects_cache.distinct("country"))
