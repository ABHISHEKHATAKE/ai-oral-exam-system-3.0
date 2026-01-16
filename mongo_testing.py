from pymongo import MongoClient
import os

# Local MongoDB
local_client = MongoClient("mongodb://localhost:27017")
local_db = local_client["exam_system_db"]   # <-- correct DB

# Atlas MongoDB
atlas_client = MongoClient(os.getenv("MONGODB_URI"))
atlas_db = atlas_client["exam_system_db"]   # same name on cloud

for col_name in local_db.list_collection_names():
    local_col = local_db[col_name]
    atlas_col = atlas_db[col_name]

    # Clear Atlas collection
    atlas_col.delete_many({})

    data = list(local_col.find())
    if data:
        atlas_col.insert_many(data)
        print(f"✅ Migrated {len(data)} records from {col_name}")
    else:
        print(f"⚠️ {col_name} empty")

print("🎉 Clean migration completed!")
