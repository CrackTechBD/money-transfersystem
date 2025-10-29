FROM python:3.11-slim

WORKDIR /app

COPY fraud_admin_dashboard/requirements.txt .
RUN pip install -r requirements.txt

COPY fraud_admin_dashboard/main.py /app/main.py

EXPOSE 8008

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]