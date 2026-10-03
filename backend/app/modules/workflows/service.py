from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Connection, Membership, Workflow, WorkflowVersion
from app.modules.connectors.registry import get_catalog
from app.modules.workflows.schemas import (
    ConnectorCapabilityResponse,
    OrganizationConnectionSummary,
    WorkflowCreateRequest,
    WorkflowDetailResponse,
    WorkflowSummaryResponse,
    WorkflowUpdateRequest,
    WorkflowVersionSummary,
)
from app.modules.workflows.validation import validate_workflow_or_raise


def _get_membership(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> Membership:
    query = select(Membership).where(Membership.user_id == user_id)
    if organization_id is not None:
        query = query.where(Membership.organization_id == organization_id)

    membership = db.scalar(query.order_by(Membership.id))
    if not membership:
        raise ValueError("User does not belong to the specified organization")
    return membership


def _assert_can_read(membership: Membership) -> None:
    if membership.role not in {"Admin", "Editor", "Viewer"}:
        raise PermissionError("User role does not have permission to view workflows")


def _assert_can_mutate(membership: Membership) -> None:
    if membership.role not in {"Admin", "Editor"}:
        raise PermissionError("Viewer role does not have permission to manage workflows")


def _to_detail_response(
    workflow: Workflow,
    target_version: WorkflowVersion,
    versions: list[WorkflowVersion],
) -> WorkflowDetailResponse:
    # An active version exists if and only if the workflow is currently published
    active_version = None
    if workflow.status == "published":
        active_version = next(
            (v for v in sorted(versions, key=lambda x: x.version_number, reverse=True) if v.published_at is not None),
            None,
        )

    version_summaries = [
        WorkflowVersionSummary(
            id=v.id,
            version_number=v.version_number,
            created_by=v.created_by,
            created_at=v.created_at,
            published_at=v.published_at,
            is_active=bool(active_version and v.id == active_version.id),
        )
        for v in versions
    ]

    return WorkflowDetailResponse(
        id=workflow.id,
        organization_id=workflow.organization_id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        version_number=target_version.version_number,
        definition=target_version.definition,
        created_by=workflow.created_by,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        versions=version_summaries,
    )


def create_workflow(
    db: Session,
    user_id: int,
    data: WorkflowCreateRequest,
    organization_id: int | None = None,
) -> WorkflowDetailResponse:
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_mutate(membership)

    # Validate the initial workflow definition
    validate_workflow_or_raise(data.definition)

    now = datetime.now(timezone.utc)
    workflow = Workflow(
        organization_id=membership.organization_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        status="draft",
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(workflow)
    db.flush()

    initial_version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        definition=data.definition.model_dump(),
        created_by=user_id,
        created_at=now,
        published_at=None,
    )
    db.add(initial_version)
    db.commit()
    db.refresh(workflow)
    db.refresh(initial_version)

    return _to_detail_response(workflow, initial_version, [initial_version])


def list_workflows(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
    status_filter: str | None = None,
) -> list[WorkflowSummaryResponse]:
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_read(membership)

    query = (
        select(Workflow)
        .where(Workflow.organization_id == membership.organization_id)
        .order_by(Workflow.updated_at.desc())
    )
    if status_filter:
        query = query.where(Workflow.status == status_filter)

    workflows = db.scalars(query).all()
    results: list[WorkflowSummaryResponse] = []

    for wf in workflows:
        latest_version = db.scalar(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == wf.id)
            .order_by(WorkflowVersion.version_number.desc())
        )
        version_num = latest_version.version_number if latest_version else 1

        results.append(
            WorkflowSummaryResponse(
                id=wf.id,
                organization_id=wf.organization_id,
                name=wf.name,
                description=wf.description,
                status=wf.status,
                version_number=version_num,
                created_by=wf.created_by,
                created_at=wf.created_at,
                updated_at=wf.updated_at,
            )
        )

    return results


def get_workflow(
    db: Session,
    user_id: int,
    workflow_id: int,
    organization_id: int | None = None,
    version_number: int | None = None,
) -> WorkflowDetailResponse:
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_read(membership)

    workflow = db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == membership.organization_id,
        )
    )
    if not workflow:
        raise ValueError("Workflow not found")

    versions = db.scalars(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
    ).all()

    if not versions:
        raise ValueError("Workflow has no recorded versions")

    if version_number is not None:
        target_version = next((v for v in versions if v.version_number == version_number), None)
        if not target_version:
            raise ValueError(f"Version {version_number} not found for workflow {workflow_id}")
    else:
        target_version = versions[0]

    return _to_detail_response(workflow, target_version, versions)


def update_workflow(
    db: Session,
    user_id: int,
    workflow_id: int,
    data: WorkflowUpdateRequest,
    target_version_number: int | None = None,
    organization_id: int | None = None,
) -> WorkflowDetailResponse:
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_mutate(membership)

    workflow = db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == membership.organization_id,
        )
    )
    if not workflow:
        raise ValueError("Workflow not found")

    now = datetime.now(timezone.utc)
    if data.name is not None:
        workflow.name = data.name.strip()
    if data.description is not None:
        workflow.description = data.description.strip() if data.description else None

    # Load version history
    versions = db.scalars(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
    ).all()
    latest_version = versions[0] if versions else None
    target_version = latest_version

    if target_version_number is not None:
        # Client explicitly targeted a specific version
        target_v = next((v for v in versions if v.version_number == target_version_number), None)
        if not target_v:
            raise ValueError(f"Version {target_version_number} not found for workflow {workflow_id}")

        if data.definition is not None:
            if target_v.published_at is not None:
                raise ValueError(
                    f"Cannot modify version {target_version_number}: Published workflow versions are immutable"
                )
            validate_workflow_or_raise(data.definition)
            target_v.definition = data.definition.model_dump()
            target_version = target_v
    elif data.definition is not None:
        validate_workflow_or_raise(data.definition)

        # Invariant: If latest version was published, editing spawns a new draft version
        if latest_version and latest_version.published_at is not None:
            new_version = WorkflowVersion(
                workflow_id=workflow.id,
                version_number=latest_version.version_number + 1,
                definition=data.definition.model_dump(),
                created_by=user_id,
                created_at=now,
                published_at=None,
            )
            db.add(new_version)
            workflow.status = "draft"
            target_version = new_version
        elif latest_version:
            # Update existing unpublished draft version
            latest_version.definition = data.definition.model_dump()
            target_version = latest_version
        else:
            new_version = WorkflowVersion(
                workflow_id=workflow.id,
                version_number=1,
                definition=data.definition.model_dump(),
                created_by=user_id,
                created_at=now,
                published_at=None,
            )
            db.add(new_version)
            target_version = new_version

    workflow.updated_at = now
    db.commit()
    db.refresh(workflow)
    if target_version:
        db.refresh(target_version)

    all_versions = db.scalars(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
    ).all()

    return _to_detail_response(workflow, target_version or all_versions[0], all_versions)


def delete_workflow(
    db: Session,
    user_id: int,
    workflow_id: int,
    organization_id: int | None = None,
) -> None:
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_mutate(membership)

    workflow = db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == membership.organization_id,
        )
    )
    if not workflow:
        raise ValueError("Workflow not found")

    db.delete(workflow)
    db.commit()


def publish_workflow(
    db: Session,
    user_id: int,
    workflow_id: int,
    organization_id: int | None = None,
) -> WorkflowDetailResponse:
    """
    Validates and publishes a workflow.

    Dual Semantics:
      - Draft + /publish:
          Validates and publishes the latest draft version, stamping published_at.
          Makes the target version active and supersedes older versions.
      - Paused + /publish:
          Resumes the existing published version without mutating versions or definitions.
          Re-verifies active connector connections and restores execution eligibility.

    Invariants:
      1. Authenticates & verifies Admin/Editor organization membership.
      2. Runs complete workflow definition validation.
      3. Verifies all referenced connectors have an active organization connection.
      4. Enforces single active published version per workflow (active versions <= 1).
      5. Commits state atomically.
    """
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_mutate(membership)

    workflow = db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == membership.organization_id,
        )
    )
    if not workflow:
        raise ValueError("Workflow not found")

    versions = db.scalars(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
    ).all()
    if not versions:
        raise ValueError("Workflow has no recorded versions to publish")

    latest_version = versions[0]
    draft_version = next((v for v in versions if v.published_at is None), None)

    if draft_version:
        target_version = draft_version
    elif workflow.status == "paused":
        target_version = latest_version
    elif workflow.status == "published":
        raise ValueError("Workflow is already published")
    else:
        target_version = latest_version

    # 1. Run complete workflow validation
    wf_def = validate_workflow_or_raise(target_version.definition)

    # 2. Check every referenced connector has an active connection in this organization
    referenced_connectors: set[str] = {wf_def.trigger.connector}
    for step in wf_def.steps:
        if getattr(step, "type", None) == "action" and hasattr(step, "connector"):
            referenced_connectors.add(step.connector)

    active_conns = db.scalars(
        select(Connection.connector_slug).where(
            Connection.organization_id == membership.organization_id,
            Connection.status == "active",
            Connection.connector_slug.in_(referenced_connectors),
        )
    ).all()
    active_slugs = set(active_conns)

    missing_connectors = referenced_connectors - active_slugs
    if missing_connectors:
        missing_list = ", ".join(f"'{c}'" for c in sorted(missing_connectors))
        raise ValueError(
            f"Cannot publish workflow: The following connectors do not have an active connection in this organization: {missing_list}"
        )

    # 3. State transition
    now = datetime.now(timezone.utc)
    if target_version.published_at is None:
        target_version.published_at = now
    workflow.status = "published"
    workflow.updated_at = now

    db.commit()
    db.refresh(workflow)
    db.refresh(target_version)

    all_versions = db.scalars(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
    ).all()

    return _to_detail_response(workflow, target_version, all_versions)


def pause_workflow(
    db: Session,
    user_id: int,
    workflow_id: int,
    organization_id: int | None = None,
) -> WorkflowDetailResponse:
    """
    Pauses an active workflow.
    Invariants:
      1. Authenticates & verifies Admin/Editor organization membership.
      2. Requires current status to be 'published'.
      3. Transitions status to 'paused' without altering versions or definition.
      4. Commits state atomically.
    """
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_mutate(membership)

    workflow = db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == membership.organization_id,
        )
    )
    if not workflow:
        raise ValueError("Workflow not found")

    if workflow.status != "published":
        raise ValueError(
            f"Cannot pause workflow with status '{workflow.status}'. Only 'published' workflows can be paused."
        )

    now = datetime.now(timezone.utc)
    workflow.status = "paused"
    workflow.updated_at = now

    db.commit()
    db.refresh(workflow)

    versions = db.scalars(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .order_by(WorkflowVersion.version_number.desc())
    ).all()

    return _to_detail_response(workflow, versions[0], versions)


def get_workflow_capabilities(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> list[ConnectorCapabilityResponse]:
    """
    Returns available connector capabilities dynamically resolved from the connector registry,
    correlated with configured connections for the active organization.
    Security guarantee:
      - Credentials and secret tokens are NEVER exposed.
      - Connections are strictly scoped to the user's active organization.
    """
    membership = _get_membership(db, user_id, organization_id)
    _assert_can_read(membership)

    conns_query = (
        select(Connection)
        .where(Connection.organization_id == membership.organization_id)
        .order_by(Connection.id.asc())
    )
    connections = db.execute(conns_query).scalars().all()

    connections_by_slug: dict[str, list[OrganizationConnectionSummary]] = {}
    for c in connections:
        connections_by_slug.setdefault(c.connector_slug, []).append(
            OrganizationConnectionSummary(
                id=c.id,
                name=c.name,
                status=c.status,
                created_at=c.created_at,
                last_tested_at=c.last_tested_at,
            )
        )

    catalog = get_catalog()
    capabilities: list[ConnectorCapabilityResponse] = []
    for item in catalog:
        slug = item["slug"]
        org_conns = connections_by_slug.get(slug, [])
        capabilities.append(
            ConnectorCapabilityResponse(
                slug=slug,
                name=item["name"],
                category=item["category"],
                description=item["description"],
                icon=item["icon"],
                is_connected=len(org_conns) > 0,
                connections=org_conns,
                supported_triggers=item["supported_triggers"],
                supported_actions=item["supported_actions"],
            )
        )

    return capabilities


def get_connector_capability(
    db: Session,
    user_id: int,
    connector_slug: str,
    organization_id: int | None = None,
) -> ConnectorCapabilityResponse:
    """
    Returns capabilities and connection availability for a single connector.
    """
    capabilities = get_workflow_capabilities(db, user_id, organization_id)
    for cap in capabilities:
        if cap.slug == connector_slug:
            return cap
    raise ValueError(f"Unknown connector slug '{connector_slug}'")

