FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY fraud_action_service/requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY fraud_action_service/main.py /app/main.py
COPY common /app/common

EXPOSE 8007

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]