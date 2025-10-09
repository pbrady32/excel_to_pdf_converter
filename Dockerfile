FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OUTPUT_BUCKET=""
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/service-account.json"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
