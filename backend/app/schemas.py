from pydantic import BaseModel
from datetime import datetime

class JobBase(BaseModel):
    id: int
    source: str
    external_id: str
    title: str
    employer: str
    city: str
    region: str
    published_at: datetime
    description: str
    url: str

    class Config:
        from_attributes = True

class LeadIn(BaseModel):
    job_id: int
    tier: str | None = None
    notes: str | None = None

class LeadOut(BaseModel):
    id: int
    job_id: int
    tier: str
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
