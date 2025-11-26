"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[str] = None
    expiration_date: str


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements (within start and expiration dates)
    """
    current_time = datetime.now().isoformat()
    
    # Build query for active announcements
    query = {
        "expiration_date": {"$gte": current_time}
    }
    
    # Filter by start_date if it exists
    announcements = []
    for announcement in announcements_collection.find(query).sort("created_at", -1):
        # Check if start_date is set and if we're past it, or if no start_date
        start_date = announcement.get("start_date")
        if start_date is None or start_date <= current_time:
            announcement["id"] = str(announcement.pop("_id"))
            announcements.append(announcement)
    
    return announcements


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """
    Get all announcements (requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    announcements = []
    for announcement in announcements_collection.find().sort("created_at", -1):
        announcement["id"] = str(announcement.pop("_id"))
        announcements.append(announcement)
    
    return announcements


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(announcement: AnnouncementCreate, teacher_username: str = Query(...)) -> Dict[str, Any]:
    """
    Create a new announcement (requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    # Validate expiration date is in the future
    try:
        expiration = datetime.fromisoformat(announcement.expiration_date.replace("Z", "+00:00"))
        if expiration < datetime.now():
            raise HTTPException(
                status_code=400, detail="Expiration date must be in the future")
        
        # Validate start_date if provided
        if announcement.start_date:
            start = datetime.fromisoformat(announcement.start_date.replace("Z", "+00:00"))
            if start >= expiration:
                raise HTTPException(
                    status_code=400, detail="Start date must be before expiration date")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    # Create announcement document
    announcement_doc = {
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date,
        "created_by": teacher_username,
        "created_at": datetime.now().isoformat()
    }
    
    result = announcements_collection.insert_one(announcement_doc)
    announcement_doc["id"] = str(result.inserted_id)
    announcement_doc.pop("_id", None)
    
    return announcement_doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    announcement: AnnouncementUpdate,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Update an existing announcement (requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    from bson import ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Check if announcement exists
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Build update document
    update_doc = {}
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date
    if announcement.expiration_date is not None:
        # Validate expiration date
        try:
            expiration = datetime.fromisoformat(announcement.expiration_date.replace("Z", "+00:00"))
            if expiration < datetime.now():
                raise HTTPException(
                    status_code=400, detail="Expiration date must be in the future")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        
        update_doc["expiration_date"] = announcement.expiration_date
    
    if not update_doc:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Update announcement
    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_doc}
    )
    
    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update announcement")
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": obj_id})
    updated["id"] = str(updated.pop("_id"))
    
    return updated


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str = Query(...)) -> Dict[str, str]:
    """
    Delete an announcement (requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    from bson import ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
