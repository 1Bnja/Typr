-- Equivalent to Alembic revisions 0004 and 0005 for an existing Typr
-- database in the public schema. Run only against a database at revision 0003.
-- Use this instead of running the Alembic upgrade separately.
BEGIN;

LOCK TABLE public.alembic_version IN EXCLUSIVE MODE;

DO $$
BEGIN
    IF (SELECT array_agg(version_num::text) FROM public.alembic_version)
        IS DISTINCT FROM ARRAY['0003']::text[] THEN
        RAISE EXCEPTION 'Expected exactly Alembic revision 0003; no changes applied';
    END IF;
END
$$;

CREATE TABLE public.auth_sessions (
    id uuid PRIMARY KEY,
    user_id integer NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    idle_expires_at timestamptz NOT NULL,
    absolute_expires_at timestamptz NOT NULL,
    revoked_at timestamptz
);

CREATE INDEX ix_auth_sessions_user_id ON public.auth_sessions (user_id);

ALTER TABLE public.auth_sessions ADD COLUMN last_practice_notice bigint;

UPDATE public.alembic_version
SET version_num = '0005'
WHERE version_num = '0003';

COMMIT;
