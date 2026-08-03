"""Users API."""

from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/me")
async def read_current_user(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user's profile.

    Exposes real fields already present on the User model. Note the frontend
    also expects a "role" (learner/admin) concept from the login response, but
    the backend only has an `is_ops` boolean -- there is no true role field to
    return here. Flagged separately rather than fabricated.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "is_ops": current_user.is_ops,
    }
