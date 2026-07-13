from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv(override=True)

Base = declarative_base()

URL_DATABASE = os.getenv("DB_URL")
if not URL_DATABASE:
    raise RuntimeError(
        "DB_URL is not set. Add it to .env (see .env.example). "
        "Example: postgresql+asyncpg://postgres:postgres@localhost:5432/project_vl"
    )

engine = create_async_engine(
    URL_DATABASE,
    echo=False,
    pool_pre_ping=True,
)

sessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def import_models() -> None:
    from app.models.user_models.User import User
    from app.models.user_models.Token import Token
    from app.models.ai_models.answer import Answer
    from app.models.ai_models.step_follow_up import StepFollowUp
    from app.models.classroom_models.Classroom import Classroom
    from app.models.classroom_models.ClassroomMembership import ClassroomMembership
    from app.models.classroom_models.Assignment import Assignment
    from app.models.classroom_models.AssignmentSubmission import AssignmentSubmission
    from app.models.subscription_models.Subscription import Subscription

    _ = (User, Token, Answer, StepFollowUp, Classroom, ClassroomMembership, Assignment, AssignmentSubmission, Subscription)


async def get_db():
    async with sessionLocal() as db:
        yield db


async def _patch_legacy_answers_blueprint_column() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE answers ADD COLUMN IF NOT EXISTS blueprint JSONB"
            )
        )


async def _patch_legacy_users_role_column() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'student'"
            )
        )


async def init_models():
    import_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _patch_legacy_answers_blueprint_column()
    await _patch_legacy_users_role_column()