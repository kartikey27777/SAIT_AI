from fastapi import APIRouter, Depends

from backend.services.auth import get_api_key
from backend.services.website import run_sync_in_thread, get_status, WEBSITE_TAGS

router = APIRouter()


@router.post("/website/sync", dependencies=[Depends(get_api_key)])
async def website_sync():
    run_sync_in_thread()
    return {
        "message": "College website sync started in background.",
        "tags": WEBSITE_TAGS,
        "status_url": "/website/status",
    }


@router.get("/website/status")
async def website_status():
    return get_status()