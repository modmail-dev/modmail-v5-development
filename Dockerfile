# Based on https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1 UV_NO_DEFAULT_GROUPS=1

# Use the system Python and do not download another Python version
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /bot
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --all-extras --no-install-project
COPY . /bot
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-extras \
    && rm /bot/uv.lock

# Then, use a final image without uv (must match the Python used in the builder)
FROM python:3.14-slim-trixie

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# Copy the application from the builder
COPY --from=builder --chown=nonroot:nonroot /bot /bot

# Place executables in the environment at the front of the path
ENV PATH="/bot/.venv/bin:$PATH"

# Use the non-root user to run our application
USER nonroot

# Use `/bot` as the working directory
WORKDIR /bot

CMD ["python", "start.py"]
