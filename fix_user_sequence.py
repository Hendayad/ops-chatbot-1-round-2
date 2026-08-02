"""One-off fix: resync the "user" table's auto-increment sequence with its actual max id.

Root cause: at some point rows got inserted into "user" with explicit id
values (bypassing the sequence) -- likely from the various diagnostic/demo
scripts run earlier in this project's life. Postgres's sequence for a
SERIAL/IDENTITY column only advances on inserts that go *through* the
sequence (the normal DEFAULT-value path), so it never learned about those
explicit-id rows. The next normal insert (e.g. a new user registering)
asks the sequence for nextval(), gets an id that was already manually
used, and collides -- IntegrityError: duplicate key value violates unique
constraint "user_pkey".

Fix: point the sequence at max(id) so future nextval() calls resume past
whatever's actually in the table. Safe to run any time, including when
there's no desync (it's a no-op then).
"""

from sqlalchemy import text

from app.services.database import database_service

with database_service.engine.connect() as conn:
    result = conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('"user"', 'id'),
                COALESCE((SELECT MAX(id) FROM "user"), 1)
            )
            """
        )
    )
    new_value = result.scalar()
    conn.commit()
    print(f"user_id sequence resynced -- next new user will get id > {new_value}")
