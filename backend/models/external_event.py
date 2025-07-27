from pydantic import BaseModel, Field
from datetime import datetime

class ExternalEventSchema(BaseModel):
    doctorId: str = Field(..., description="Doctor ID linked to event")
    eventId: str = Field(..., description="Google/Outlook event ID")
    source: str = Field(..., regex="^(google|outlook)$")
    summary: str = Field(..., description="Event title or subject")
    startTime: datetime = Field(..., description="Event start time in UTC (ISO format)")
    endTime: datetime = Field(..., description="Event end time in UTC (ISO format)")
    calendarId: str = Field(..., description="Calendar identifier (e.g., 'primary')")
    fetchedAt: datetime = Field(default_factory=datetime.utcnow)
