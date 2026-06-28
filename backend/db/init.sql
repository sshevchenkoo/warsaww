-- Tables are created by the app on startup (Base.metadata.create_all),
-- this file only enables the extensions search needs:
--   vector  → semantic search   |   pg_trgm → lexical leg of hybrid search.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
