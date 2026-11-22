"""Clear a text's stored ideal time when its record holder is deleted."""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION reset_deleted_holder_ideal_time() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            -- The FK action runs after the user is deleted. Explicitly
            -- unlinking a still-existing holder must not change the time.
            IF NOT EXISTS (SELECT 1 FROM public.users WHERE id = OLD.record_user_id) THEN
                NEW.ideal_time_ms := NULL;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER reset_deleted_holder_ideal_time
        BEFORE UPDATE OF record_user_id ON texts
        FOR EACH ROW
        WHEN (OLD.record_user_id IS NOT NULL AND NEW.record_user_id IS NULL)
        EXECUTE FUNCTION reset_deleted_holder_ideal_time()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER reset_deleted_holder_ideal_time ON texts")
    op.execute("DROP FUNCTION reset_deleted_holder_ideal_time()")
