from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from .database import Base

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, index=True, nullable=False)
    external_id = Column(String, index=True, nullable=False)

    title = Column(String, nullable=False, default="")
    employer = Column(String, nullable=False, default="")
    city = Column(String, nullable=False, default="")
    region = Column(String, nullable=False, default="")
    url = Column(String, nullable=False, default="")
    description = Column(String, nullable=False, default="")
    published_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_provider_external"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "external_id": self.external_id,
            "title": self.title,
            "employer": self.employer,
            "city": self.city,
            "region": self.region,
            "url": self.url,
            "description": self.description,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }
