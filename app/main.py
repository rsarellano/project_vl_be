"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("uvicorn.error")

_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path, override=True)

from app.connection.database import init_models
from app.controllers.main_router import router

_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
if not _api_key:
    logger.warning("OPENAI_API_KEY is missing. Add it to %s and restart the server.", _env_path)
elif len(_api_key) < 40 or _api_key == "sk-your-key-here":
    logger.warning(
        "OPENAI_API_KEY looks like a placeholder (%s). Paste your real key into %s and restart.",
        _env_path.name,
        _env_path,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_models()
    except Exception as exc:
        logger.warning(
            "Database init failed (%s). Start Postgres (see docker-compose.yml) and restart. "
            "Answer generation will still work; user auth will not.",
            exc,
        )
    yield


app = FastAPI(title="Project VL API", version="0.1.0", lifespan=lifespan)

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

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
