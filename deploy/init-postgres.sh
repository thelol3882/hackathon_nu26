#!/bin/bash
# Create the separate database for Report Service.
# This script runs automatically on first postgres container start
# (mounted into /docker-entrypoint-initdb.d/).

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE locomotive_reports;
    GRANT ALL PRIVILEGES ON DATABASE locomotive_reports TO $POSTGRES_USER;
EOSQL
