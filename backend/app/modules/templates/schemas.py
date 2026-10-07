from datetime import datetime
from pydantic import BaseModel, ConfigDict

class TemplateBase(BaseModel):
    name: str
    description: str
    category: str
    difficulty: str
    industry_tags: list[str]
    app_slugs: list[str]

class TemplateSummary(TemplateBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class TemplateDetail(TemplateSummary):
    definition: dict
    setup_schema: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
