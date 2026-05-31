"""FastAPI application entrypoint."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.answer_router import answer_router

load_dotenv()

app = FastAPI(title="Project VL API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(answer_router, prefix="/api/answers", tags=["answers"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
