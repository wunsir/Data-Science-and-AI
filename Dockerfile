FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    JOBS_SEED_DB_PATH=/app/artifacts/jobs_seed.sqlite \
    JOBS_DB_PATH=/tmp/finding_jobs/jobs.sqlite \
    WEBSITE_DIR=/app/website

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps . \
    && python scripts/rebuild.py --output-dir artifacts \
    && mkdir -p website/data/charts /tmp/finding_jobs \
    && cp artifacts/analysis_summary.json website/data/analysis_summary.json \
    && cp -R artifacts/charts/. website/data/charts/

EXPOSE 7860

CMD ["sh", "-c", "cp /app/artifacts/jobs_seed.sqlite /tmp/finding_jobs/jobs.sqlite && exec uvicorn finding_jobs.app:app --host 0.0.0.0 --port 7860"]
