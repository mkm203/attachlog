"""Placement service: run with  uvicorn app.main:app --port 8001"""
from fastapi import FastAPI

from app.auth import router as auth_router
from app.database import Base, engine
from app.errors import register_handlers
from app.routes import router

Base.metadata.create_all(engine)

app = FastAPI(title="AttachLog Placement Service", version="1.0.0",
              description="Placements managed by the coordinator once per term. "
                          "Get a token from POST /v1/auth/login, then click Authorize.")
register_handlers(app)
app.include_router(auth_router)
app.include_router(router)


@app.get("/health", tags=["health"])
def health():
    """Liveness/readiness probe."""
    return {"status": "ok", "service": "placement"}