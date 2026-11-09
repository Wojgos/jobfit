-- Separate database for the test suite (created on first start of the db container).
CREATE DATABASE jobfit_test OWNER jobfit;
\connect jobfit
CREATE EXTENSION IF NOT EXISTS vector;
\connect jobfit_test
CREATE EXTENSION IF NOT EXISTS vector;
