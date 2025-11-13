from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from app.controllers.main_router import router
from app.connection.database import init_models

async def lifespan(app):
    await init_models()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.1.9:5173"],
    allow_credentials=True,       # Allows cookies, authorization headers
    allow_methods=["*"],          # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],
)

app.include_router(router)
