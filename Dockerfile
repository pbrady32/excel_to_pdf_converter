FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

# Copy pyproject (and optional lockfile/requirements if present)
COPY pyproject.toml uv.lock* requirements.txt* ./

COPY pyproject.toml uv.lock* ./
# Install dependencies defined in pyproject via uv sync
RUN uv sync --no-cache

COPY . .
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${PORT:-8080}"]
