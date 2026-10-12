# Multi-stage lightweight Python Dockerfile for WeatherGuard AI
FROM python:3.12-slim

# Prevent Python from writing .pyc and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose ports for FastAPI and Streamlit
EXPOSE 8000 8501

# Default command (can be overridden by compose service definitions)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
