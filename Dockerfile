FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

# copy metadata first so dependency installation layer caches well
COPY pyproject.toml uv.lock* ./

# copy package source needed while uv sync installs “excel-to-pdf-converter”
COPY app ./app

# install dependencies (includes project since package=true)
RUN uv sync --no-cache

# copy the remainder of the repo
COPY . .

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
