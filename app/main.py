
from fastapi import FastAPI
from app.controllers.main_router import router
from app.connection.database import init_models

async def lifespan(app):
    await init_models()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(router)

