# File: backend/app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .settings import settings

# Skapar databasmotorn
engine = create_async_engine(settings.database_url, future=True, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db():
    # Enkel kontroll av databasanslutning
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
