FROM python:3.13.9-slim-trixie
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY apps/extractor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && groupadd -g 10002 office && useradd -u 10002 -g 10002 -M -d /nonexistent office
COPY apps/extractor/app.py /app/app.py
COPY apps/extractor/office_structure.py /app/office_structure.py
COPY apps/extractor/xlsx_print.py /app/xlsx_print.py
COPY apps/extractor/ods_print.py /app/ods_print.py
USER 10002:10002
EXPOSE 8001
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8001","--workers","1"]
