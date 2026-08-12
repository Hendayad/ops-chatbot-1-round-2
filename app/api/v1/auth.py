"""Authentication and authorization endpoints for the API.

This module provides endpoints for user registration, login, session management,
and token verification.
"""

import uuid
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.config import settings
from sqlalchemy import text
from app.core.limiter import limiter
from app.core.logging import (
    bind_context,
    logger,
)
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import (
    PublicCohort,
    SessionResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.database import database_service
from app.utils.auth import (
    create_access_token,
    verify_token,
)
from app.utils.sanitization import (
    sanitize_email,
    sanitize_string,
    validate_password_strength,
)

router = APIRouter()
security = HTTPBearer()
db_service = database_service  # shared singleton -- do not construct a new pool here

NO_COHORT_ID = "no-cohort"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Get the current user ID from the token.

    Args:
        credentials: The HTTP authorization credentials containing the JWT token.

    Returns:
        User: The user extracted from the token.

    Raises:
        HTTPException: If the token is invalid or missing.
    """
    try:
        # Sanitize token
        token = sanitize_string(credentials.credentials)

        user_id = verify_token(token)
        if user_id is None:
            logger.error("invalid_token", token_part=token[:10] + "...")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify user exists in database
        user_id_int = int(user_id)
        user = await db_service.get_user(user_id_int)
        if user is None:
            logger.error("user_not_found", user_id=user_id_int)
            raise HTTPException(
                status_code=404,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Bind user_id to logging context for all subsequent logs in this request
        bind_context(user_id=user_id_int)

        return user
    except ValueError as ve:
        logger.exception("token_validation_failed", error=str(ve))
        raise HTTPException(
            status_code=422,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_ops_user(user: User = Depends(get_current_user)) -> User:
    """Require the authenticated user to be Ops-authorized (User.is_ops).

    Plain sync function (no I/O of its own -- get_current_user already did
    the DB lookup), so it's directly unit-testable without a DB or HTTP
    client: construct a User and call this with it. Use as the auth
    dependency on Ops-only endpoints (e.g. app.api.v1.atrisk) instead of
    the plain get_current_user, which only proves "some authenticated
    account", not "an Ops/admin account".

    Args:
        user: The already-authenticated user (resolved via get_current_user).

    Returns:
        The same user, unchanged, once authorization is confirmed.

    Raises:
        HTTPException: 403 if the user is authenticated but not Ops-authorized.
    """
    if not user.is_ops:
        logger.warning("ops_authorization_denied", user_id=user.id)
        raise HTTPException(
            status_code=403,
            detail="This endpoint requires Ops authorization.",
        )
    return user


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Session:
    """Get the current session ID from the token.

    Args:
        credentials: The HTTP authorization credentials containing the JWT token.

    Returns:
        Session: The session extracted from the token.

    Raises:
        HTTPException: If the token is invalid or missing.
    """
    try:
        # Sanitize token
        token = sanitize_string(credentials.credentials)

        session_id = verify_token(token)
        if session_id is None:
            logger.error("session_id_not_found", token_part=token[:10] + "...")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Sanitize session_id before using it
        session_id = sanitize_string(session_id)

        # Verify session exists in database
        session = await db_service.get_session(session_id)
        if session is None:
            logger.error("session_not_found", session_id=session_id)
            raise HTTPException(
                status_code=404,
                detail="Session not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Bind user_id to logging context for all subsequent logs in this request
        bind_context(user_id=session.user_id)

        return session
    except ValueError as ve:
        logger.exception("token_validation_failed", error=str(ve))
        raise HTTPException(
            status_code=422,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _sync_expired_cohorts() -> None:
    """Persist expired cohort status in the database.

    A cohort is expired only after its end date has passed. A cohort whose
    end date is today remains available through today.
    """
    with db_service.get_session_maker() as session:
        result = session.execute(
            text(
                """
                UPDATE cohort
                SET enabled = FALSE
                WHERE enabled = TRUE
                  AND end_date IS NOT NULL
                  AND end_date < CURRENT_DATE
                """
            )
        )

        if result.rowcount:
            session.commit()
            logger.info(
                "expired_cohorts_disabled",
                count=result.rowcount,
            )


def _get_enabled_registration_cohorts() -> list[dict[str, str]]:
    """Return enabled, non-expired cohorts from the database."""
    _sync_expired_cohorts()

    with db_service.get_session_maker() as session:
        rows = session.execute(
            text(
                """
                SELECT cohort_id, name
                FROM cohort
                WHERE enabled = TRUE
                  AND (
                      end_date IS NULL
                      OR end_date >= CURRENT_DATE
                  )
                ORDER BY name, cohort_id
                """
            )
        ).mappings().all()

    return [
        {
            "cohort_id": str(row["cohort_id"]).strip(),
            "name": str(row["name"]).strip(),
        }
        for row in rows
        if row["cohort_id"] and row["name"]
    ]


def _get_enabled_cohort(cohort_id: str) -> str | None:
    """Return the canonical ID when the requested cohort is currently active."""
    normalized_cohort_id = cohort_id.strip().lower()
    if not normalized_cohort_id:
        return None

    _sync_expired_cohorts()

    with db_service.get_session_maker() as session:
        row = session.execute(
            text(
                """
                SELECT cohort_id
                FROM cohort
                WHERE LOWER(cohort_id) = :cohort_id
                  AND enabled = TRUE
                  AND (
                      end_date IS NULL
                      OR end_date >= CURRENT_DATE
                  )
                LIMIT 1
                """
            ),
            {"cohort_id": normalized_cohort_id},
        ).mappings().first()

    if row is None:
        return None

    return str(row["cohort_id"]).strip()


@router.get("/cohorts", response_model=list[PublicCohort])
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["register"][0])
async def list_registration_cohorts(request: Request) -> list[PublicCohort]:
    """Return only enabled cohorts that may be selected during registration."""
    cohorts = _get_enabled_registration_cohorts()

    return [
        PublicCohort(
            cohort_id=cohort["cohort_id"],
            name=cohort["name"],
        )
        for cohort in cohorts
    ]


@router.post("/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["register"][0])
async def register_user(request: Request, user_data: UserCreate):
    """Register a new user.

    Args:
        request: The FastAPI request object for rate limiting.
        user_data: User registration data

    Returns:
        UserResponse: The created user info
    """
    try:
        # Sanitize email
        sanitized_email = sanitize_email(user_data.email)

        # Extract and validate password
        password = user_data.password.get_secret_value()
        validate_password_strength(password)

        # Check if user exists
        if await db_service.get_user_by_email(sanitized_email):
            raise HTTPException(
                status_code=400,
                detail="Email already registered",
            )

        # Sanitize learner identity fields
        sanitized_username = (
            sanitize_string(user_data.username)
            if user_data.username
            else None
        )

        first_name = sanitize_string(user_data.first_name)
        last_name = sanitize_string(user_data.last_name)

        if not first_name or not last_name:
            raise HTTPException(
                status_code=422,
                detail="First name and last name are required",
            )

        # -----------------------------
        # Cohort validation
        # -----------------------------

        requested_cohort_id = sanitize_string(
            user_data.cohort_id
        ).strip()

        available_cohorts = _get_enabled_registration_cohorts()

        if requested_cohort_id == NO_COHORT_ID:
            # "no-cohort" is accepted only when there are genuinely no
            # enabled cohorts available for registration.
            if available_cohorts:
                raise HTTPException(
                    status_code=400,
                    detail="A cohort must be selected",
                )

            cohort_id = NO_COHORT_ID

        else:
            cohort_id = _get_enabled_cohort(requested_cohort_id)

            if cohort_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid, disabled, or expired cohort",
                )

        # -----------------------------
        # Create user after validation
        # -----------------------------

        user = await db_service.create_user(
            email=sanitized_email,
            password=User.hash_password(password),
            username=sanitized_username,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            cohort_id=cohort_id,
        )

        token = create_access_token(str(user.id))

        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            cohort_id=(
                user.cohort_id.strip().lower()
                if user.cohort_id
                else NO_COHORT_ID
            ),
            token=token,
        )

    except ValueError as ve:
        logger.exception("user_registration_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["login"][0])
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    grant_type: str = Form(default="password"),
):
    """Login a user."""

    try:
        # Sanitize inputs
        email = sanitize_string(email)
        password = sanitize_string(password)
        grant_type = sanitize_string(grant_type)

        # Verify grant type
        if grant_type != "password":
            raise HTTPException(
                status_code=400,
                detail="Unsupported grant type. Must be 'password'",
            )

        # Get user
        user = await db_service.get_user_by_email(email)

        if user is None or not user.verify_password(password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create JWT
        token = create_access_token(str(user.id))

        logger.info(
            "user_logged_in",
            user_id=user.id,
            role=user.role.value,
        )

        return TokenResponse(
            access_token=token.access_token,
            token_type="bearer",
            expires_at=token.expires_at,
            role=user.role.value,   # <-- returns the actual database role
        )

    except ValueError as ve:
        logger.exception(
            "login_validation_failed",
            error=str(ve),
        )
        raise HTTPException(
            status_code=422,
            detail=str(ve),
        )


@router.post("/session", response_model=SessionResponse)
async def create_session(user: User = Depends(get_current_user)):
    """Create a new chat session for the authenticated user.

    Args:
        user: The authenticated user

    Returns:
        SessionResponse: The session ID, name, and access token
    """
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Create session in database, copying username for LLM personalization
        session = await db_service.create_session(session_id, user.id, username=user.username, cohort_id=user.cohort_id)

        # Create access token for the session
        token = create_access_token(session_id)

        logger.info(
            "session_created",
            session_id=session_id,
            user_id=user.id,
            name=session.name,
            expires_at=token.expires_at.isoformat(),
        )

        return SessionResponse(session_id=session_id, name=session.name, token=token)
    except ValueError as ve:
        logger.exception("session_creation_validation_failed", error=str(ve), user_id=user.id)
        raise HTTPException(status_code=422, detail=str(ve))


@router.patch("/session/{session_id}/name", response_model=SessionResponse)
async def update_session_name(
    session_id: str, name: str = Form(...), current_session: Session = Depends(get_current_session)
):
    """Update a session's name.

    Args:
        session_id: The ID of the session to update
        name: The new name for the session
        current_session: The current session from auth

    Returns:
        SessionResponse: The updated session information
    """
    try:
        # Sanitize inputs
        sanitized_session_id = sanitize_string(session_id)
        sanitized_name = sanitize_string(name)
        sanitized_current_session = sanitize_string(current_session.id)

        # Verify the session ID matches the authenticated session
        if sanitized_session_id != sanitized_current_session:
            raise HTTPException(status_code=403, detail="Cannot modify other sessions")

        # Update the session name
        session = await db_service.update_session_name(sanitized_session_id, sanitized_name)

        # Create a new token (not strictly necessary but maintains consistency)
        token = create_access_token(sanitized_session_id)

        return SessionResponse(session_id=sanitized_session_id, name=session.name, token=token)
    except ValueError as ve:
        logger.exception("session_update_validation_failed", error=str(ve), session_id=session_id)
        raise HTTPException(status_code=422, detail=str(ve))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, current_session: Session = Depends(get_current_session)):
    """Delete a session for the authenticated user.

    Args:
        session_id: The ID of the session to delete
        current_session: The current session from auth

    Returns:
        None
    """
    try:
        # Sanitize inputs
        sanitized_session_id = sanitize_string(session_id)
        sanitized_current_session = sanitize_string(current_session.id)

        # Verify the session ID matches the authenticated session
        if sanitized_session_id != sanitized_current_session:
            raise HTTPException(status_code=403, detail="Cannot delete other sessions")

        # Delete the session
        await db_service.delete_session(sanitized_session_id)

        logger.info("session_deleted", session_id=session_id, user_id=current_session.user_id)
    except ValueError as ve:
        logger.exception("session_deletion_validation_failed", error=str(ve), session_id=session_id)
        raise HTTPException(status_code=422, detail=str(ve))


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(user: User = Depends(get_current_user)):
    """Get all session IDs for the authenticated user.

    Args:
        user: The authenticated user

    Returns:
        List[SessionResponse]: List of session IDs
    """
    try:
        sessions = await db_service.get_user_sessions(user.id)
        return [
            SessionResponse(
                session_id=sanitize_string(session.id),
                name=sanitize_string(session.name),
                token=create_access_token(session.id),
            )
            for session in sessions
        ]
    except ValueError as ve:
        logger.exception("get_sessions_validation_failed", user_id=user.id, error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))