FROM python:3.11-slim
WORKDIR /app
COPY ledger_service/requirements.txt .
RUN apt-get update && apt-get install -y default-libmysqlclient-dev build-essential pkg-config \ 
    && pip install -r requirements.txt && apt-get purge -y build-essential && rm -rf /var/lib/apt/lists/*
COPY ledger_service/main.py /app/main.py
COPY ledger_service/models.py /app/models.py
COPY ledger_service/db.py /app/db.py
COPY ledger_service/outbox_worker.py /app/outbox_worker.py
COPY common /app/common
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
