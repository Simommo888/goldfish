# Multi-stage build for goldfish AI agent
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY scripts/goldfish/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.10-slim AS runtime

WORKDIR /app

# Install runtime dependencies (git for source tracking, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Set PATH for user-installed packages
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy project
COPY . /app

# Install goldfish in development mode
WORKDIR /app/scripts/goldfish
RUN pip install --no-cache-dir -e .

# Create necessary directories for outputs and config
RUN mkdir -p output_cache config

# Set working directory to project root
WORKDIR /app

# Default command: run dry-run for verification
CMD ["goldfish", "dry-run", "--verbose"]
