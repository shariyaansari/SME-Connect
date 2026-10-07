from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"


class StepType(str, Enum):
    ACTION = "action"
    CONDITION = "condition"


class TriggerDefinition(BaseModel):
    connector: str = Field(..., description="Connector slug, e.g. google_sheets")
    event: str = Field(..., description="Trigger capability slug, e.g. new_row")
    config: dict[str, Any] = Field(default_factory=dict, description="Trigger configuration")


class ActionStepDefinition(BaseModel):
    id: str = Field(..., description="Unique step identifier within the workflow")
    type: Literal["action"] = Field("action", description="Step discriminator")
    connector: str = Field(..., description="Destination connector slug, e.g. crm")
    action: str = Field(..., description="Action capability slug, e.g. create_lead")
    config: dict[str, Any] = Field(default_factory=dict, description="Action configuration")
    mapping: dict[str, Any] = Field(
        default_factory=dict,
        description="Field mappings to source paths, e.g. {'name': 'trigger.values.Name'}",
    )


class ConditionStepDefinition(BaseModel):
    id: str = Field(..., description="Unique step identifier within the workflow")
    type: Literal["condition"] = Field("condition", description="Step discriminator")
    field: str = Field(..., description="Source path to evaluate, e.g. trigger.status")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: Any | None = Field(None, description="Expected value for comparison")


WorkflowStepDefinition = Annotated[
    Union[ActionStepDefinition, ConditionStepDefinition],
    Field(discriminator="type"),
]


class WorkflowDefinition(BaseModel):
    trigger: TriggerDefinition = Field(..., description="Single workflow entry-point trigger")
    steps: list[WorkflowStepDefinition] = Field(
        ...,
        min_length=1,
        description="Ordered sequence of execution steps (actions or conditions)",
    )


class ValidationErrorItem(BaseModel):
    path: str
    message: str
    code: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)


# ============================================================================
# Workflow CRUD Request & Response Schemas (Step 3.4)
# ============================================================================

class WorkflowCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150, description="Workflow name")
    description: str | None = Field(None, max_length=1000, description="Optional workflow description")
    definition: WorkflowDefinition = Field(..., description="Initial workflow definition")
    template_id: int | None = Field(None, description="Optional source template ID")


class WorkflowUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150, description="Updated workflow name")
    description: str | None = Field(None, max_length=1000, description="Updated description")
    definition: WorkflowDefinition | None = Field(None, description="Updated workflow definition")


class WorkflowVersionSummary(BaseModel):
    id: int
    version_number: int
    created_by: int
    created_at: Any
    published_at: Any | None = None
    is_active: bool = False


class WorkflowSummaryResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None
    status: str
    version_number: int
    created_by: int
    created_at: Any
    updated_at: Any


class WorkflowDetailResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None
    status: str
    version_number: int
    definition: WorkflowDefinition
    created_by: int
    created_at: Any
    updated_at: Any
    versions: list[WorkflowVersionSummary] = Field(default_factory=list)


class OrganizationConnectionSummary(BaseModel):
    id: int
    name: str
    status: str
    created_at: Any
    last_tested_at: Any | None = None


class ConnectorCapabilityResponse(BaseModel):
    slug: str
    name: str
    category: str
    description: str
    icon: str
    is_connected: bool
    connections: list[OrganizationConnectionSummary] = Field(default_factory=list)
    supported_triggers: list[dict[str, Any]] = Field(default_factory=list)
    supported_actions: list[dict[str, Any]] = Field(default_factory=list)


