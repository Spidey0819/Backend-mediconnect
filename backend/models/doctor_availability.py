from pydantic import BaseModel, Field
from datetime import datetime

class DoctorAvailabilitySchema(BaseModel):
    doctorId: str = Field(..., description="Unique doctor identifier")
    startTime: datetime = Field(..., description="Start time in ISO format, e.g., 2025-07-04T10:00:00Z")
    endTime: datetime = Field(..., description="End time in ISO format, e.g., 2025-07-04T11:00:00Z")
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)