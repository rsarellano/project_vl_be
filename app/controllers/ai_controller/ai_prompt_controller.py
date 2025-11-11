from app.schemas.ai_schemas.prompt_receiver_schema import PromptReceiverBase
from app.services.ai_services.prompt_receiver_service import user_prompt
from app.connection.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, status, Depends


router = APIRouter(prefix="/ai_prompt",
                   tags=["ai_prompt"])


@router.post("/", response_model=PromptReceiverBase, status_code=status.HTTP_201_CREATED)
async def create_new_prompt(prompt: PromptReceiverBase, db: AsyncSession = Depends(get_db)):
    return await user_prompt(db, prompt)



# @router.post("/interpret")
# async def interpret_prompt(data: PromptReceiverBase, db: AsyncSession = Depends(get_db)):
#         try:
#                 # saved_prompt = await user_prompt(db,data)
                
#                 ai_result = await interpret_svg_prompt(data.prompt_text)
                
#                 return {
#                         "status": "success",
#                         "saved_prompt": saved_prompt,
#                         "svg_elements": ai_result
#                 }
                
                
#         except Exception as e:
#                 raise HTTPException(status_code=500, detail=str(e))
