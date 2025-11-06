
from fastapi import FastAPI
from app.services.svg_services import svg_elements_service
from app.controllers.svg_controller.svg_controller import router as svg_element_router
from app.controllers.ai_controller.ai_prompt_controller import router as ai_prompt_router
from app.db.database.database import engine, Base


app = FastAPI()


# def custom_openai():
#     if app.openai_schema:


app.include_router(svg_element_router)
app.include_router(ai_prompt_router)


@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables ensured on startup")