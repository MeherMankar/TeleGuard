# Multi-stage build for production optimization
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION=2.0.0
ARG VCS_REF

# Add metadata labels
LABEL org.opencontainers.image.title="TeleGuard" \
      org.opencontainers.image.description="Professional Telegram Account Manager with OTP Destroyer Protection" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/MeherMankar/TeleGuard" \
      org.opencontainers.image.url="https://github.com/MeherMankar/TeleGuard" \
      org.opencontainers.image.documentation="https://github.com/MeherMankar/TeleGuard/wiki" \
      org.opencontainers.image.authors="Meher Mankar <meherpatil84@gmail.com>, Gutkesh <mirrorbot01@gmail.com>" \
      org.opencontainers.image.vendor="TeleGuard" \
      org.opencontainers.image.licenses="MIT"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY config/requirements.txt ./config/
RUN pip install --no-cache-dir --user -r config/requirements.txt

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 teleguard \
    && useradd --uid 1000 --gid teleguard --shell /bin/bash --create-home teleguard

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/teleguard/.local

# Copy application code
COPY --chown=teleguard:teleguard . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/backups /app/config \
    && chown -R teleguard:teleguard /app \
    && chmod -R 755 /app

# Switch to non-root user
USER teleguard

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/teleguard/.local/bin:$PATH \
    TELEGUARD_VERSION=${VERSION}

# Health check with proper error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import asyncio, sys; \
    try: \
        from teleguard.utils.health_check import health_checker; \
        status = asyncio.run(health_checker.get_health_status()); \
        sys.exit(0 if status.get('status') == 'healthy' else 1) \
    except Exception as e: \
        print(f'Health check failed: {e}'); \
        sys.exit(1)" || exit 1

# Expose port for web interface (if enabled)
EXPOSE 8080

# Use exec form for proper signal handling
ENTRYPOINT ["python", "main.py"]

# Add build info
RUN echo "TeleGuard v${VERSION} built on ${BUILD_DATE}" > /app/build_info.txt
