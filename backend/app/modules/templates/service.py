from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Template


def list_active_templates(db: Session) -> list[Template]:
    """Returns a list of all active templates."""
    stmt = select(Template).where(Template.is_active == True).order_by(Template.id)
    return list(db.scalars(stmt).all())


def get_template(db: Session, template_id: int) -> Template | None:
    """Returns a specific template by ID."""
    stmt = select(Template).where(Template.id == template_id)
    return db.scalars(stmt).first()
