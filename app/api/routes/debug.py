from fastapi import APIRouter
from app.services.mongo_service import mongo_service

router = APIRouter(prefix="/api/debug", tags=["Debug"])


@router.get("/db")
def db_status():
    """Return MongoDB connection status and basic collection counts."""
    connected = mongo_service.is_connected()
    status = {"connected": connected}
    if not connected:
        return status

    try:
        db = mongo_service.db
        status["db_name"] = db.name
        collections = db.list_collection_names()
        counts = {}
        for c in collections:
            try:
                counts[c] = db[c].estimated_document_count()
            except Exception:
                counts[c] = None
        status["collections"] = counts
    except Exception as e:
        status["error"] = str(e)

    return status
