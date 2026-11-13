"""Logbook service: run with  uvicorn app.main:app --port 8002"""
from fastapi import FastAPI

from app.database import Base, engine
from app.errors import register_handlers
from app.routes import router

Base.metadata.create_all(engine)

app = FastAPI(title="AttachLog Logbook Service", version="1.0.0",
              description="Weekly log entries and supervisor reviews. "
                          "Get a token from the placement service (POST /v1/auth/login), then click Authorize.")
register_handlers(app)
app.include_router(router)


@app.get("/health", tags=["health"])
def health():
    """Liveness/readiness probe."""
    return {"status": "ok", "service": "logbook"}