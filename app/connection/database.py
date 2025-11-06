from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession,async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv(override=True)

Base = declarative_base()

URL_DATABASE = os.getenv("DB_URL")

engine = create_async_engine(
    URL_DATABASE,
    echo=False,
    pool_pre_ping=True,
)

sessionLocal = sessionmaker( autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False)

async def get_db():
    async with sessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)