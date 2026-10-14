FROM postgis/postgis:16-3.4

LABEL maintainer="Lapor SAR Lite Team"
LABEL description="PostgreSQL 16 with PostGIS 3.4 and pgvector extensions pre-installed"

# Install pgvector extension on top of official PostGIS image
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
