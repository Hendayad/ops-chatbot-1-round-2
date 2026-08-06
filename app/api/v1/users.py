from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.models.user import User, UserRole
from app.api.v1.auth import get_current_user
from app.services.database import database_service


router = APIRouter()

db_service = database_service


# -----------------------------
# Get all users
# ADMIN + PROGRAM_LEAD
# -----------------------------

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
                "role": user.role.value,
                "cohort": user.cohort,
                "is_ops": user.is_ops,
            }
            for user in users
        ]


# -----------------------------
# Change user role / cohort
# ADMIN + PROGRAM_LEAD
# -----------------------------

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

    with db_service.get_session_maker() as session:

        target_user = session.get(User, user_id)

        if target_user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        # PROGRAM_LEAD cannot edit another PROGRAM_LEAD
        if (
            current_user.role == UserRole.PROGRAM_LEAD
            and target_user.role == UserRole.PROGRAM_LEAD
        ):
            raise HTTPException(
                status_code=403,
                detail="Program leads cannot edit other program leads",
            )

        new_role_raw = data.get("role")

        if new_role_raw is None:
            raise HTTPException(
                status_code=400,
                detail="role is required",
            )

        try:
            new_role = UserRole(new_role_raw)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {new_role_raw}",
            )

        # Update role
        target_user.role = new_role

        # Keep is_ops in sync with role
        target_user.is_ops = new_role in (
            UserRole.ADMIN,
            UserRole.PROGRAM_LEAD,
        )

        # Only learners have a cohort
        if new_role == UserRole.LEARNER:
            target_user.cohort = data.get("cohort") or "Unassigned"
        else:
            target_user.cohort = None

        session.add(target_user)
        session.commit()
        session.refresh(target_user)

        return {
            "id": target_user.id,
            "email": target_user.email,
            "username": target_user.username,
            "role": target_user.role.value,
            "cohort": target_user.cohort,
            "is_ops": target_user.is_ops,
        }

# -----------------------------
# Current user profile
# -----------------------------

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "cohort": current_user.cohort,
        "is_ops": current_user.is_ops,
    }
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.models.user import User, UserRole
from app.api.v1.auth import get_current_user
from app.services.database import DatabaseService


router = APIRouter()

db_service = DatabaseService()


# -----------------------------
# Get all users
# ADMIN + PROGRAM_LEAD
# -----------------------------

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
                "role": user.role.value,
                "is_ops": user.is_ops,
            }
            for user in users
        ]


# -----------------------------
# Change user role
# ADMIN + PROGRAM_LEAD
# -----------------------------

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


    # Validate role dynamically from enum
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
        # Program leads can manage users,
        # but cannot promote someone to ADMIN
        # or remove ADMIN privileges.

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


        # Apply change

        user.role = requested_role


        # Keep is_ops synchronized
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
        }



# -----------------------------
# Current user profile
# -----------------------------

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "cohort": current_user.cohort,
    }


# -----------------------------
# Current user's group / teammates
# -----------------------------

@router.get("/me/teammates")
async def get_my_teammates(
    current_user: User = Depends(get_current_user),
):
    """Return the current user's group (cohort) and the teammates in it.

    Includes each teammate's email deliberately: learners are expected to be
    able to contact their group directly (rendered on the Settings page). If
    that changes, drop the field here rather than only hiding it in the UI.

    A learner with no cohort assigned yet gets an empty teammate list rather
    than an error, so the frontend can show "not assigned yet" instead of
    crashing.
    """
    if not current_user.cohort:
        return {
            "cohort": None,
            "teammates": [],
        }

    with db_service.get_session_maker() as session:

        teammates = session.exec(
            select(User)
            .where(
                User.cohort == current_user.cohort,
                User.id != current_user.id,
            )
        ).all()

        return {
            "cohort": current_user.cohort,
            "teammates": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                }
                for user in teammates
            ],
        }
