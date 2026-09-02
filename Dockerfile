# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE* ./
COPY aimake ./aimake

RUN pip install --upgrade pip \
    && pip install --prefix=/install ".[s3,huggingface,experiments]"

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="aimake" \
      org.opencontainers.image.description="Incremental build system for AI pipelines" \
      org.opencontainers.image.source="https://github.com/arjun988/aimake" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

COPY --from=builder /install /install

WORKDIR /workspace
VOLUME ["/workspace"]

ENTRYPOINT ["aimake"]
CMD ["--help"]
