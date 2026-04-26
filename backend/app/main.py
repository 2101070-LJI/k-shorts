from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import clips, edit, evolution, health, preferences, templates
from app.config import settings
from app.db.connection import init_db
from app.pipeline.evolution import scheduler as evolution_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "videos").mkdir(exist_ok=True)
    (settings.data_dir / "clips").mkdir(exist_ok=True)
    (settings.data_dir / "models").mkdir(exist_ok=True)
    init_db()
    evolution_scheduler.start()
    try:
        yield
    finally:
        evolution_scheduler.shutdown()


app = FastAPI(title="K-Shorts API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(templates.router)
app.include_router(edit.router)
app.include_router(clips.router)
app.include_router(preferences.router)
app.include_router(evolution.router)

app.mount("/clips", StaticFiles(directory=str(settings.data_dir / "clips")), name="clips")
