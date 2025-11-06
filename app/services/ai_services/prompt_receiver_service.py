from app.db.models.ai_prompt.prompt_receiver import PromptReceiver
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.ai_schemas.prompt_receiver_schema import PromptReceiverBase


async def user_prompt(db: AsyncSession, data: PromptReceiverBase):
    prompt_data = data.model_dump()
    new_prompt = PromptReceiver(**prompt_data)
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)
    return new_prompt