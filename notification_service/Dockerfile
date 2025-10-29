FROM python:3.11-slim
WORKDIR /app
COPY notification_service/requirements.txt .
RUN pip install -r requirements.txt
COPY notification_service/main.py /app/main.py
COPY common /app/common
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
