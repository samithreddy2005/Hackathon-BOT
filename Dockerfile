# syntax=docker/dockerfile:1
#
# Two stages: dependencies are built once against a wheel cache, then copied into
# a slim runtime image that carries no compiler.

# ---------------------------------------------------------------------------
# Stage 1 — build the virtual environment
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential is needed to compile any dependency without a manylinux wheel;
# it stays in this stage and never reaches the final image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies are installed before the source is copied so that editing code
# does not invalidate the (slow) dependency layer.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps .

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# tesseract-ocr enables reading resumes sent as photos. Drop this layer if you
# do not need OCR — it is roughly 100 MB.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user; a container process should never be root.
RUN useradd --create-home --uid 10001 atsbot
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Writable state lives in one place so it can be mounted as a single volume.
RUN mkdir -p /data/database /data/uploads /data/logs && chown -R atsbot:atsbot /data
ENV DATABASE_PATH=/data/database/ats_bot.db \
    UPLOAD_DIR=/data/uploads \
    LOG_DIR=/data/logs

USER atsbot
VOLUME ["/data"]

# Long polling opens no port, so the check verifies the process can still import
# and configure itself rather than probing a socket.
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "from ats_bot.config import Settings; Settings.from_env()" || exit 1

ENTRYPOINT ["ats-bot"]
