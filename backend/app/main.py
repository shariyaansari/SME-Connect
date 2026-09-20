from fastapi import FastAPI

from app.database.connection import Base, engine
from app.database import models
from app.modules.auth.router import router as auth_router
from app.modules.organizations.router import router as organization_router


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SME Connect API",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(organization_router)

@app.get("/")
def root():
    return {
        "message": "SME Connect API is running"
    }