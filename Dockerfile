FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app/backend
COPY payload/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY payload/backend/ ./
COPY payload/frontend-v2/ /app/frontend-v2/
EXPOSE 9500
CMD ["python", "-m", "uvicorn", "run_local:app", "--host", "0.0.0.0", "--port", "9500"]
