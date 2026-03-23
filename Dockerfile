FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# Using UID/GID 1000 for compatibility with common development environments
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Install Python dependencies as root (required for system-wide packages)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code, tests, and Alembic config
COPY src/ ./src/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Set ownership of application files to non-root user
RUN chown -R appuser:appuser /app

RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Switch to non-root user for running the application
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
