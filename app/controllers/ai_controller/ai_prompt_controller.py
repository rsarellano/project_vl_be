from app.schemas.ai_schemas.prompt_receiver_schema import PromptReceiverBase
from app.services.ai_services.prompt_receiver_service import user_prompt
from app.db.database.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, status, Depends


router = APIRouter(prefix="/ai_prompt",
                   tags=["ai_prompt"])


@router.post("/", response_model=PromptReceiverBase, status_code=status.HTTP_201_CREATED)
async def create_new_prompt(prompt: PromptReceiverBase, db: AsyncSession = Depends(get_db)):
    return await user_prompt(db, prompt)