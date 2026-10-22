from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import health
from backend.app.routers import artifacts
from backend.app.routers import journeys
from backend.app.routers import requirements
from backend.app.routers import execution
from backend.app.routers import analysis


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

ARTIFACTS_DIR = BASE_DIR / "artifacts"


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="AI Test Intelligence",
    description=(
        "AI-powered Test Intelligence and TestOps platform "
        "for UI exploration, test generation, execution, "
        "failure analysis, self-healing and coverage."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    health.router,
    prefix="/api",
)

app.include_router(
    artifacts.router,
    prefix="/api",
)

app.include_router(
    journeys.router,
    prefix="/api",
)

app.include_router(
    requirements.router,
    prefix="/api",
)

app.include_router(
    execution.router,
    prefix="/api",
)

app.include_router(
    analysis.router,
    prefix="/api",
)

# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "name": "AI Test Intelligence",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )