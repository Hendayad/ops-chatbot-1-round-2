"""Ops Console KB admin API — re-ingest, list, and retire knowledge base materials."""

import re
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from app.api.v1.auth import get_current_user
from app.cohorts.config import (
    CohortAlreadyExistsError,
    CohortConfigError,
    CohortDefinition,
    CohortNotFoundError,
    MaterialNotFoundError,
    cohort_config,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.ingestion.loader import load_materials
from app.kb.schema import SourceType
from app.kb.store import build_default_store
from app.models.user import User
from app.schemas.knowledge import IngestionStats, RawMaterial

router = APIRouter()

_SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,199}$")
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

TYPE_TO_DIR = {
    SourceType.FAQ: "faqs",
    SourceType.SCHEDULE: "schedules",
    SourceType.ONBOARDING: "onboarding",
    SourceType.PROGRAM_DOC: "docs",
}


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


# ----------------------------------------------------------------------
# Cohort schemas (create / update payloads, response shapes)
# ----------------------------------------------------------------------


class MaterialOut(BaseModel):
    title: str
    source: str
    type: SourceType


class CohortOut(BaseModel):
    cohort_id: str
    name: str
    materials_root: str
    enabled: bool
    description: str | None = None
    project: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    materials: list[MaterialOut]

    @classmethod
    def from_definition(cls, definition: CohortDefinition) -> "CohortOut":
        return cls(
            cohort_id=definition.cohort_id,
            name=definition.name,
            materials_root=definition.materials_root,
            enabled=definition.enabled,
            description=definition.description,
            project=definition.project,
            start_date=definition.start_date,
            end_date=definition.end_date,
            materials=[
                MaterialOut(title=m.title, source=m.source, type=m.type)
                for m in definition.materials
            ],
        )


class CohortCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    materials_root: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=2000)
    project: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class CohortUpdateIn(BaseModel):
    """Partial update. Omitted fields are left unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=2000)
    project: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    clear_description: bool = False
    clear_project: bool = False
    clear_start_date: bool = False
    clear_end_date: bool = False


class MaterialAddOut(BaseModel):
    cohort: CohortOut
    material: MaterialOut


# ----------------------------------------------------------------------
# Cohort routes
# ----------------------------------------------------------------------


@router.get("/cohorts")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def list_cohorts(
    request: Request,
    include_disabled: bool = False,
    user: User = Depends(get_current_user),
):
    """List every cohort declared in the configuration file (M10 / F3.4).

    BUGFIX: previously called ``load_cohort_config`` per id, which uses
    ``.get()`` internally and therefore only ever returns *enabled*
    cohorts — a disabled cohort's id from ``list_cohorts()`` would silently
    come back as an empty placeholder dict. This now reads full definitions
    directly so disabled cohorts render correctly when requested.
    """
    definitions = cohort_config.list_definitions(include_disabled=include_disabled)
    return {"cohorts": [CohortOut.from_definition(d) for d in definitions]}


@router.get("/cohorts/{cohort_id}")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def get_cohort(
    request: Request,
    cohort_id: str,
    user: User = Depends(get_current_user),
):
    """Return one cohort's full detail, including its materials."""
    definition = cohort_config.get_any(cohort_id)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Cohort {cohort_id!r} not found.")
    return CohortOut.from_definition(definition)


@router.post("/cohorts", status_code=201)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def create_cohort(
    request: Request,
    payload: CohortCreateIn,
    user: User = Depends(get_current_user),
):
    """Create a new cohort. The cohort id is derived from ``name``."""
    try:
        definition = cohort_config.create_cohort(
            name=payload.name,
            materials_root=payload.materials_root,
            description=payload.description,
            project=payload.project,
            start_date=payload.start_date,
            end_date=payload.end_date,
            enabled=payload.enabled,
        )
    except CohortAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CohortConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("cohort_created", user_id=user.id, cohort=definition.cohort_id)
    return CohortOut.from_definition(definition)


@router.patch("/cohorts/{cohort_id}")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def update_cohort(
    request: Request,
    cohort_id: str,
    payload: CohortUpdateIn,
    user: User = Depends(get_current_user),
):
    """Update mutable fields (name, enabled, description, project, dates)."""
    kwargs: dict = {"name": payload.name, "enabled": payload.enabled}
    kwargs["description"] = None if payload.clear_description else (
        payload.description if payload.description is not None else ...
    )
    kwargs["project"] = None if payload.clear_project else (
        payload.project if payload.project is not None else ...
    )
    kwargs["start_date"] = None if payload.clear_start_date else (
        payload.start_date if payload.start_date is not None else ...
    )
    kwargs["end_date"] = None if payload.clear_end_date else (
        payload.end_date if payload.end_date is not None else ...
    )

    try:
        definition = cohort_config.update_cohort(cohort_id, **kwargs)
    except CohortNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CohortConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("cohort_updated", user_id=user.id, cohort=definition.cohort_id)
    return CohortOut.from_definition(definition)


@router.delete("/cohorts/{cohort_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def delete_cohort(
    request: Request,
    cohort_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a cohort, its files, and all KB embeddings."""

    try:
        # Delete every chunk belonging to this cohort from the KB
        store = build_default_store()
        store.retire_cohort(cohort_id)

        # Delete the cohort configuration and files
        cohort_config.delete_cohort(cohort_id)

    except CohortNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.exception(
            "cohort_delete_failed",
            user_id=user.id,
            cohort=cohort_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(
        "cohort_deleted",
        user_id=user.id,
        cohort=cohort_id,
    )


@router.post("/cohorts/{cohort_id}/materials", response_model=MaterialAddOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def upload_material(
    request: Request,
    cohort_id: str,
    title: str = Form(..., min_length=1, max_length=300),
    material_type: SourceType = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload one material file for a cohort and register it in the config.

    This only saves the file and records it in ``cohorts_config.json`` — it
    does not embed/index the content. Run the existing
    ``POST /cohorts/{cohort_id}/onboard`` (or ``/reingest``) afterwards to
    pull it into the knowledge base.
    """
    definition = cohort_config.get_any(cohort_id)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Cohort {cohort_id!r} not found.")

    filename = file.filename or ""
    safe_name = Path(filename).name  # drop any directory components
    if not safe_name or not _SAFE_FILENAME_PATTERN.fullmatch(safe_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid file name. Use letters, numbers, spaces, dots, "
                "hyphens, or underscores only."
            ),
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
        )

    subdirectory = TYPE_TO_DIR.get(material_type)

    if subdirectory is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported material type: {material_type}",
        )

    materials_dir = (
        cohort_config.materials_base_dir
        / definition.materials_root
        / subdirectory
    )

    materials_dir.mkdir(parents=True, exist_ok=True)

    destination = materials_dir / safe_name

    # Resolve and double-check the final path stays inside materials_dir,
    # even though safe_name is already sanitized above (defense in depth).
    resolved_dir = materials_dir.resolve()
    resolved_dest = destination.resolve()
    if resolved_dir not in resolved_dest.parents and resolved_dest != resolved_dir:
        raise HTTPException(status_code=400, detail="Invalid file destination.")

    if destination.exists():
        raise HTTPException(
            status_code=409,
            detail=f"A file named '{safe_name}' already exists for this cohort.",
        )

    destination.write_bytes(contents)

    try:
        updated = cohort_config.add_material(
            cohort_id,
            title=title,
            source=safe_name,
            type=material_type,
        )
    except CohortConfigError as e:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    added = next(m for m in updated.materials if m.source == safe_name)
    logger.info(
        "cohort_material_uploaded",
        user_id=user.id,
        cohort=updated.cohort_id,
        source=safe_name,
    )
    return MaterialAddOut(
        cohort=CohortOut.from_definition(updated),
        material=MaterialOut(title=added.title, source=added.source, type=added.type),
    )


@router.delete("/cohorts/{cohort_id}/materials/{source:path}")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def remove_material(
    request: Request,
    cohort_id: str,
    source: str,
    delete_file: bool = False,
    user: User = Depends(get_current_user),
):
    """Unregister a material from a cohort, optionally deleting the file too."""
    try:
        updated = cohort_config.remove_material(cohort_id, source)
    except CohortNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MaterialNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    store = build_default_store()
    store.retire_material(source)   # or the correct source_id

    if delete_file:
    # Find the material type from the original cohort definition
        definition = cohort_config.get_any(cohort_id)

        if definition:
            removed_material = next(
                (m for m in definition.materials if m.source == source),
                None,
            )

            if removed_material:
                subdirectory = TYPE_TO_DIR.get(removed_material.type)

                if subdirectory:
                    materials_dir = (
                        cohort_config.materials_base_dir
                        / definition.materials_root
                        / subdirectory
                    )

                    target = (materials_dir / source).resolve()

                    if materials_dir.resolve() in target.parents:
                        target.unlink(missing_ok=True)

    logger.info("cohort_material_removed", user_id=user.id, cohort=cohort_id, source=source)
    return CohortOut.from_definition(updated)


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


@router.get("/materials/{material_id:path}")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["kb_admin"][0])
async def get_material(
    request: Request,
    material_id: str,
    user: User = Depends(get_current_user),
):
    """Fetch a single material's full content."""
    try:
        store = build_default_store()
        material = store.get_material(material_id)

        if not material:
            raise HTTPException(
                status_code=404,
                detail=f"No material found for material_id={material_id}",
            )

        logger.info(
            "kb_material_fetched",
            user_id=user.id,
            material_id=material_id,
        )

        return material

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            "kb_material_fetch_failed",
            user_id=user.id,
            material_id=material_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retire/{material_id:path}")
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

        return {"material_id": material_id, "retired": True}

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            "kb_retire_failed",
            user_id=user.id,
            material_id=material_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))