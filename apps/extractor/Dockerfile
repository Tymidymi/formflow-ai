FROM python:3.13.9-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY apps/extractor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && groupadd -g 10002 docling \
    && useradd -u 10002 -g 10002 -M -d /nonexistent docling
COPY apps/extractor/app.py /app/app.py
USER 10002:10002
EXPOSE 8001
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8001","--workers","1"]
