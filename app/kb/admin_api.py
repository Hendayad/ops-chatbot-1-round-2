"""Ops Console KB admin API — re-ingest, list, and retire knowledge base materials."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.auth import get_current_user
from app.cohorts.config import cohort_config
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.ingestion.loader import load_materials
from app.kb.store import build_default_store
from app.models.user import User
from app.schemas.knowledge import IngestionStats, RawMaterial

router = APIRouter()


@router.post("/reingest", response_model=IngestionStats)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def reingest_materials(
    request: Request,
    materials: list[RawMaterial],
    user: User = Depends(get_current_user),
):
    """Re-ingest a batch of approved materials into the knowledge base."""
    try:
        store = build_default_store()
        stats = store.ingest(materials)

        logger.info(
            "kb_reingest_completed",
            user_id=user.id,
            sources_seen=stats.sources_seen,
        )

        return stats

    except Exception as e:
        logger.exception(
            "kb_reingest_failed",
            user_id=user.id,
            error=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/cohorts")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def list_cohorts(
    request: Request,
    user: User = Depends(get_current_user),
):
    """List every cohort declared in the configuration file (M10 / F3.4)."""
    cohorts = [cohort_config.load_cohort_config(cohort_id) for cohort_id in cohort_config.list_cohorts()]
    return {"cohorts": cohorts}


@router.post("/cohorts/{cohort_id}/onboard", response_model=IngestionStats)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def onboard_cohort(
    request: Request,
    cohort_id: str,
    user: User = Depends(get_current_user),
):
    """Launch a cohort from its configuration entry and supplied materials.

    This is the "no rebuild" path required by F3.4: the cohort's id and its
    materials directory come from the configuration file, and every loaded
    material is stamped with that cohort id, so nothing here can ingest one
    cohort's files under another cohort's name.
    """
    if not cohort_config.is_known_cohort(cohort_id):
        raise HTTPException(status_code=404, detail=f"Cohort {cohort_id!r} is not in the cohort configuration.")

    config = cohort_config.load_cohort_config(cohort_id)
    materials_root = config["materials_root"]
    if not materials_root:
        raise HTTPException(status_code=400, detail=f"Cohort {cohort_id!r} has no materials_root configured.")

    try:
        materials = load_materials(materials_root, config["cohort_id"])
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not materials:
        raise HTTPException(status_code=400, detail=f"No approved materials found under {materials_root!r}.")

    try:
        store = build_default_store()
        stats = store.ingest(materials)
        logger.info(
            "cohort_onboarded",
            user_id=user.id,
            cohort=config["cohort_id"],
            materials=len(materials),
            sources_seen=stats.sources_seen,
        )
        return stats
    except Exception as e:
        logger.exception("cohort_onboarding_failed", user_id=user.id, cohort=cohort_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/materials")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def list_materials(
    request: Request,
    user: User = Depends(get_current_user),
):
    """List all materials currently in the knowledge base, with freshness info."""
    try:
        store = build_default_store()
        materials = store.list_materials()

        logger.info(
            "kb_materials_listed",
            user_id=user.id,
            count=len(materials),
        )

        return {"materials": materials}

    except Exception as e:
        logger.exception(
            "kb_list_failed",
            user_id=user.id,
            error=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post("/retire/{material_id}")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def retire_material(
    request: Request,
    material_id: str,
    user: User = Depends(get_current_user),
):
    """Retire a material from the knowledge base."""
    try:
        store = build_default_store()

        retired = store.retire_material(material_id)

        if not retired:
            raise HTTPException(
                status_code=404,
                detail=f"No material found for material_id={material_id}",
            )

        logger.info(
            "kb_material_retired_via_api",
            user_id=user.id,
            material_id=material_id,
        )

        return {
            "material_id": material_id,
            "retired": True,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            "kb_retire_failed",
            user_id=user.id,
            material_id=material_id,
            error=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
