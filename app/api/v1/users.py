from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.models.user import User, UserRole
from app.api.v1.auth import get_current_user
from app.services.database import DatabaseService


router = APIRouter()

db_service = DatabaseService()


# -----------------------------
# Get all users (ADMIN only)
# -----------------------------

@router.get("/")
async def get_users(
    current_user: User = Depends(get_current_user)
):

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )


    with db_service.get_session_maker() as session:

        users = session.exec(
            select(User)
        ).all()


        return [
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role.value
            }
            for user in users
        ]



# -----------------------------
# Change user role
# -----------------------------

@router.patch("/{user_id}/role")
async def update_user_role(
    user_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    new_role = data.get("role", "").strip().lower()

    if new_role not in ["learner", "admin"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid role",
        )

    with db_service.get_session_maker() as session:

        user = session.get(User, user_id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        user.role = UserRole(new_role)

        session.add(user)
        session.commit()
        session.refresh(user)

        return {
            "message": "Role updated successfully",
            "user_id": user.id,
            "new_role": user.role.value,
        }