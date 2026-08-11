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
class UserCreate(BaseModel):
    email: str
    username: str
    first_name: str
    last_name: str
    password: str
    role: str = "learner"
    cohort_id: int | None = None


class AdminPasswordReset(BaseModel):
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
# Create a new user
# ADMIN + PROGRAM_LEAD
# ============================================================

@router.post("/")
async def create_user(
    data: UserCreate,
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

    email = data.email.strip().lower()
    username = data.username.strip()
    password = data.password.strip()
    new_role = data.role.strip().lower()

    if not email or not username or not password:
        raise HTTPException(
            status_code=400,
            detail="Email, username, and password are required.",
        )

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    valid_roles = {role.value.lower() for role in UserRole}

    if new_role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail="Invalid role",
        )

    requested_role = UserRole(new_role)


    with db_service.get_session_maker() as session:

        existing = session.exec(
            select(User).where(
                (User.email == email) | (User.username == username)
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="A user with that email or username already exists.",
            )

        is_staff = requested_role in (
            UserRole.ADMIN,
            UserRole.PROGRAM_LEAD,
        )

        user = User(
            email=email,
            username=username,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            hashed_password=User.hash_password(password),
            role=requested_role,
            cohort_id=None if is_staff else data.cohort_id,
            is_ops=is_staff,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        return {
            "message": "User created successfully.",
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
        }


# ============================================================
# Admin reset of another user's password
# ADMIN + PROGRAM_LEAD
# ============================================================

@router.patch("/{user_id}/password")
async def admin_reset_password(
    user_id: int,
    data: AdminPasswordReset,
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

    password = data.password.strip()

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    with db_service.get_session_maker() as session:
        user = session.get(User, user_id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found.",
            )

        user.hashed_password = User.hash_password(password)

        session.add(user)
        session.commit()

    return {"message": "Password reset successfully."}


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