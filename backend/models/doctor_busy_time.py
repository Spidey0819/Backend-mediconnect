from pydantic import BaseModel, Field
from datetime import datetime

class DoctorBusyTimeSchema(BaseModel):
    doctorId: str = Field(..., description="Unique doctor identifier")
    startTime: datetime = Field(..., description="Busy start time in ISO format")
    endTime: datetime = Field(..., description="Busy end time in ISO format")
    reason: str = Field(..., description="Reason for unavailability")
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
