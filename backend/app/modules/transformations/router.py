from fastapi import APIRouter, Depends, status
from app.core.security import get_current_user
from app.database.models import User
from app.modules.transformations.engine import (
    evaluate_transformation,
    extract_value,
    get_transformations_catalog,
)
from app.modules.transformations.schemas import (
    MappingPreviewRequest,
    MappingPreviewResponse,
    TransformationCatalogItem,
)

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows & Transformations"],
)


@router.get(
    "/transforms/catalog",
    response_model=list[TransformationCatalogItem],
)
def get_transform_catalog_endpoint(
    current_user: User = Depends(get_current_user),
):
    """
    Returns full catalog of supported data transformations, their parameters,
    and schema examples.
    """
    return get_transformations_catalog()


@router.post(
    "/mapping/preview",
    response_model=MappingPreviewResponse,
)
def preview_mapping_endpoint(
    payload: MappingPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Test-evaluates field mappings and transformations against sample context.
    Returns the resolved output dictionary, count of fields, and any evaluation errors.
    """
    resolved_output = {}
    errors = []
    mapping = payload.mapping or {}
    context = payload.sample_context or {}

    for target_key, expr in mapping.items():
        try:
            val = extract_value(expr, context)
            resolved_output[target_key] = val
        except Exception as err:
            errors.append(f"Field '{target_key}': {str(err)}")
            resolved_output[target_key] = None

    return MappingPreviewResponse(
        output=resolved_output,
        fields_evaluated=len(mapping),
        success=len(errors) == 0,
        errors=errors,
    )
