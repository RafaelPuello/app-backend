FROM python:3.12 AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Create a user to avoid running containers as root in production
RUN addgroup --system web \
    && adduser --system --ingroup web --home /home/web web \
    && chown -R web:web /home/web

# Install os-level dependencies (as root)
RUN set -ex && apt-get update && apt-get install -y --no-install-recommends \
    # dependencies for building Python packages      
    build-essential \
    # cleaning up unused files to reduce the image size
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for the source code and use it as base path
WORKDIR /home/web/code
RUN chown -R web:web /home/web/code

# Create static directory and set permissions
RUN mkdir -p /home/web/code/static \
    && chown -R web:web /home/web/code/static

# Switch to the non-root user
USER web

# Copy the python depencencies list for pip
COPY --chown=web:web ./requirements.txt requirements.txt

USER root
RUN pip install --no-cache-dir -r requirements.txt
USER web

# Entrypoint script
COPY --chown=web:web entrypoint.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/entrypoint.sh
USER web

#ENTRYPOINT ["entrypoint.sh"]



# ===========================
# Dev image
# ===========================
FROM base AS dev

# Install extra packages required in development
USER root
COPY --chown=web:web requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
USER web

# Copy the scripts that starts the development application server (runserver)
COPY --chown=web:web start-dev-server.sh /usr/local/bin
USER root
RUN chmod +x /usr/local/bin/start-dev-server.sh
USER web

# The development server starts by default when the container starts
CMD ["start-dev-server.sh"]


# ===========================
# Prod image
# ===========================
FROM base AS prod

USER web
WORKDIR /home/web/code

# Copy everything for production
COPY --chown=web:web . ./

COPY --chown=web:web start-prod-server.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/start-prod-server.sh
USER web

# The production server starts by default when the container starts
CMD ["start-prod-server.sh"]