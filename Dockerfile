FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-docker.txt .
RUN pip install --no-cache-dir --default-timeout=300 --retries=5 -r requirements-docker.txt

COPY backend/ ./backend/

RUN mkdir -p /app/uploads

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]