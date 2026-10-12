from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class TransformationType(str, Enum):
    CONCAT = "concat"
    TRIM = "trim"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    TITLECASE = "titlecase"
    REPLACE = "replace"
    SUBSTRING = "substring"
    DEFAULT_VALUE = "default_value"
    TO_STRING = "to_string"
    TO_NUMBER = "to_number"
    TO_INTEGER = "to_integer"
    TO_BOOLEAN = "to_boolean"
    FORMAT_DATE = "format_date"


class TransformationCatalogItem(BaseModel):
    type: str
    name: str
    description: str
    category: str
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    example: dict[str, Any] = Field(default_factory=dict)


class MappingPreviewRequest(BaseModel):
    mapping: dict[str, Any] = Field(
        ...,
        description="Field mapping dictionary with direct paths, template strings, or structured transform objects",
    )
    sample_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Sample execution context (e.g. {'trigger': {'values': {...}}, 'steps': {...}})",
    )


class MappingPreviewResponse(BaseModel):
    output: dict[str, Any]
    fields_evaluated: int
    success: bool
    errors: list[str] = Field(default_factory=list)
