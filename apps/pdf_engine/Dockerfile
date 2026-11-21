FROM python:3.13.9-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/pdf_engine/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
  && groupadd -g 10003 pdfworker \
  && useradd -u 10003 -g 10003 -M -d /nonexistent pdfworker
COPY apps/pdf_engine/engine.py /app/engine.py
COPY apps/pdf_engine/app.py /app/app.py
USER 10003:10003
EXPOSE 8002
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8002","--workers","1"]
