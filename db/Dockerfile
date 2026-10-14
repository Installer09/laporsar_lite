FROM postgis/postgis:16-3.4

LABEL maintainer="Lapor SAR Lite Team"
LABEL description="PostgreSQL 16 with PostGIS 3.4 and pgvector extensions pre-installed"

# Fix PostgreSQL APT archive repository for Debian Bullseye and install pgvector
RUN sed -i 's|http://apt.postgresql.org/pub/repos/apt/|https://apt-archive.postgresql.org/pub/repos/apt/|g' /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
