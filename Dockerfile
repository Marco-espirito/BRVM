FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app app
COPY data /data
RUN mkdir -p /var/data

EXPOSE 10000
CMD ["sh", "-c", "python -m app.import_data && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]