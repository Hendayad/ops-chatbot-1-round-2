from sqlmodel import select

from app.models.user import User
from app.profile.schema import LearnerProfile
from app.services.database import database_service


class DatabaseProfileRepository:
    def __init__(self):
        """Initialize the database repository."""
        self.db = database_service

    async def load(self, user_id: str) -> LearnerProfile:

        with self.db.get_session_maker() as session:

            user = session.exec(
                select(User).where(User.id == int(user_id))
            ).first()

            if not user:
                return LearnerProfile()

            return LearnerProfile(
                preferred_name=user.preferred_name,
                timezone=user.timezone,
                cohort=user.cohort_id,
            )

    async def save(
        self,
        user_id: str,
        profile: LearnerProfile,
    ):

        with self.db.get_session_maker() as session:

            user = session.exec(
                select(User).where(User.id == int(user_id))
            ).first()

            if user is None:
                return

            user.preferred_name = profile.preferred_name
            user.timezone = profile.timezone
            user.cohort_id = profile.cohort

            session.add(user)
            session.commit()