# Dockerfile-postgres

# Base Image
FROM postgres:15-alpine

# Copy the initialization script
# Postgres automatically runs any .sql files found in this directory on startup
# Build context is new-backend root, so we reference database/init.sql
COPY database/init.sql /docker-entrypoint-initdb.d/

# SECURITY NOTE:
# We do NOT set passwords here (ENV POSTGRES_PASSWORD).
# The password will be injected by Kubernetes from your root .env file.