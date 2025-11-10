from app.models.ai_models.prompt_receiver import PromptReceiver
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.ai_schemas.prompt_receiver_schema import PromptReceiverBase
import re
import json
import os
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI



api_key = os.getenv("OPENAI_API_KEY")



async def user_prompt(db: AsyncSession, data: PromptReceiverBase):
    prompt_data = data.model_dump()
    new_prompt = PromptReceiver(**prompt_data)
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)
    return new_prompt


async def interpret_svg_prompt(prompt: str):
    
    template = PromptTemplate.from_template("""
    You are an SVG generator AI.
                                            
    Use the available SVG element templates provided below to construct
    a meaningful composition based on the user's prompt.
                                            
                                            """)
    
    final_prompt = template.format(
        user_prompt=prompt,
        element_catalog = element_catalog
    )
    
    
    llm = ChatOpenAI(
        temperature = 0.3,
        model="gpt-4o-mini",
        open_api_key=api_key
    )
    
    
    response = llm.invoke(final_prompt)
    raw = response.content.strip()
    
    clean_json = re.sub(r"^```(?:json)?\s*|```$", "", raw, flags=re.IGNORECASE | re.MULTILINE)


    try:
        result = json.loads(clean_json)
    except Exception as e:
        print("JSON parse error", e)
        result = []
        
    return result