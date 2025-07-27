from pydantic import BaseModel, Field
from typing import List
from datetime import time
from bson import ObjectId

class DoctorScheduleSettingsSchema(BaseModel):
    doctorId: str  # Will convert to ObjectId in the route
    workingHours: dict = Field(..., example={"start": "09:00", "end": "17:00"})
    workingDays: List[str] = Field(..., example=["Monday", "Tuesday", "Wednesday"])
    consultationDuration: int  # in minutes (e.g., 30, 45, 60)
