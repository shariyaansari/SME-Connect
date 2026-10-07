from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database.connection import Base, engine
from app.database import models  # noqa: F401
from app.modules.auth.router import router as auth_router
from app.modules.organizations.router import router as organization_router
from app.modules.connectors.router import router as connectors_router
from app.modules.workflows.router import router as workflows_router
from app.modules.workflows.execution_router import router as executions_router
from app.modules.templates.router import router as templates_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        from app.database.connection import SessionLocal
        from app.modules.templates.seed import seed_templates
        with SessionLocal() as db:
            seed_templates(db)
    except Exception as exc:
        print(f"[Warning] Could not initialize database tables or seed templates at startup: {exc}")
    yield


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SME Connect API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(connectors_router)
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(templates_router)



@app.get("/")
def root():
    return {
        "message": "SME Connect API is running"
    }
