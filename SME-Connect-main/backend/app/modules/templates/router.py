from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.modules.templates import schemas, service

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[schemas.TemplateSummary])
@router.get("/", response_model=list[schemas.TemplateSummary])
def get_templates(db: Session = Depends(get_db)):
    """
    List all active templates.
    """
    return service.list_active_templates(db)


@router.get("/{template_id}", response_model=schemas.TemplateDetail)
def get_template(template_id: int, db: Session = Depends(get_db)):
    """
    Get the full definition and setup schema for a specific template.
    """
    template = service.get_template(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return template
