FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for MySQL
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY shard_manager_service/requirements.txt .
RUN pip install -r requirements.txt

# Copy application files
COPY shard_manager_service/main.py /app/main.py
COPY common /app/common

# Set environment variables
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]