-- Initial DB setup for APS
-- Runs once when Postgres container starts with empty volume

SET TIME ZONE 'Asia/Seoul';

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Alembic will manage the rest of the schema.
