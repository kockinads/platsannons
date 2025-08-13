# backend/app/schemas.py
from pydantic import BaseModel
from datetime import datetime

class JobOut(BaseModel):
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
        from_attributes = True  # pydantic v2: gör att vi kan skapa från SQLAlchemy-objekt

class LeadCreate(BaseModel):
    job_id: int
    tier: str | None = None
    notes: str | None = None

class LeadOut(BaseModel):
    id: int
    job_id: int
    tier: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
