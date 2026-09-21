from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database.connection import Base, engine
from app.database import models  # noqa: F401
from app.modules.auth.router import router as auth_router
from app.modules.organizations.router import router as organization_router
from app.modules.connectors.router import router as connectors_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        print(f"[Warning] Could not initialize database tables at startup: {exc}")
    yield


app = FastAPI(
    title="SME Connect API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(connectors_router)



@app.get("/")
def root():
    return {
        "message": "SME Connect API is running"
    }