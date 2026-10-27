FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY legacy_api legacy_api

EXPOSE 8000
# APP_MODULE=legacy_api.main:app runs the mock legacy system from the same image.
CMD ["sh", "-c", "uvicorn ${APP_MODULE:-app.main:app} --host 0.0.0.0 --port ${PORT:-8000}"]
