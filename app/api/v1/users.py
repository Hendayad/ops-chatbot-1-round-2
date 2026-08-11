from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.models.user import User, UserRole
from app.api.v1.auth import get_current_user
from app.services.database import database_service


router = APIRouter()

db_service = database_service


# ============================================================
# Request schemas
# ============================================================

class PasswordUpdate(BaseModel):
    password: str


# ============================================================
# Get all users
# ADMIN + PROGRAM_LEAD
# ============================================================

@router.get("/")
async def get_users(
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PROGRAM_LEAD,
    ):
        raise HTTPException(
            status_code=403,
            detail="Admin or program lead access required",
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
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,
                "cohort_id": user.cohort_id,
                "is_ops": user.is_ops,
            }
            for user in users
        ]


# ============================================================
# Current user profile
# ============================================================

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_ops": current_user.is_ops,
        "cohort_id": current_user.cohort_id,
    }


# ============================================================
# Create / change current user's password
# ============================================================
@router.patch("/me/password")
async def update_my_password(
    data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
):
    password = data.password.strip()

    if not password:
        raise HTTPException(
            status_code=400,
            detail="Password cannot be empty.",
        )

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    new_password_hash = User.hash_password(password)

    with db_service.get_session_maker() as session:
        user = session.get(User, current_user.id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found.",
            )

        user.hashed_password = new_password_hash

        session.add(user)
        session.commit()

    return {
        "message": "Password updated successfully.",
    }


# ============================================================
# Current user's group / teammates
# ============================================================

@router.get("/me/teammates")
async def get_my_teammates(
    current_user: User = Depends(get_current_user),
):
    """
    Return the current user's group and teammates.

    A learner without a cohort gets an empty teammate list.
    """

    if not current_user.cohort_id:
        return {
            "cohort_id": None,
            "teammates": [],
        }

    with db_service.get_session_maker() as session:

        teammates = session.exec(
            select(User)
            .where(
                User.cohort_id == current_user.cohort_id,
                User.id != current_user.id,
            )
        ).all()

        return {
            "cohort_id": current_user.cohort_id,
            "teammates": [
                {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": user.role.value,
                }
                for user in teammates
            ],
        }


# ============================================================
# Change user role
# ADMIN + PROGRAM_LEAD
# ============================================================

@router.patch("/{user_id}/role")
async def update_user_role(
    user_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PROGRAM_LEAD,
    ):
        raise HTTPException(
            status_code=403,
            detail="Admin or program lead access required",
        )

    new_role = data.get("role", "").strip().lower()
    new_cohort = data.get("cohort")

    # -----------------------------------
    # Validate role
    # -----------------------------------

    valid_roles = {
        role.value.lower()
        for role in UserRole
    }

    if new_role not in valid_roles:
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

        requested_role = UserRole(new_role)

        # -----------------------------------
        # Prevent removing your own admin role
        # -----------------------------------

        losing_admin = (
            user.role == UserRole.ADMIN
            and requested_role != UserRole.ADMIN
        )

        if user.id == current_user.id and losing_admin:
            raise HTTPException(
                status_code=400,
                detail="You cannot remove your own admin role.",
            )

        # -----------------------------------
        # Prevent removing last admin
        # -----------------------------------

        if losing_admin:

            admins = session.exec(
                select(User)
                .where(User.role == UserRole.ADMIN)
            ).all()

            if len(admins) == 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove the last remaining admin.",
                )

        # -----------------------------------
        # Program Lead restrictions
        # -----------------------------------

        if current_user.role == UserRole.PROGRAM_LEAD:

            if requested_role == UserRole.ADMIN:
                raise HTTPException(
                    status_code=403,
                    detail="Program leads cannot assign admin roles.",
                )

            if (
                user.role == UserRole.ADMIN
                and requested_role != UserRole.ADMIN
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Program leads cannot demote admins.",
                )

        # -----------------------------------
        # Apply role
        # -----------------------------------

        user.role = requested_role

        # -----------------------------------
        # Update cohort
        # -----------------------------------

        if requested_role in (
            UserRole.ADMIN,
            UserRole.PROGRAM_LEAD,
        ):
            user.cohort_id = None
        else:
            user.cohort_id = new_cohort

        # -----------------------------------
        # Keep is_ops synchronized
        # -----------------------------------

        user.is_ops = (
            user.role in (
                UserRole.ADMIN,
                UserRole.PROGRAM_LEAD,
            )
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        return {
            "message": "Role updated successfully",
            "user_id": user.id,
            "new_role": user.role.value,
            "cohort_id": user.cohort_id,
        }