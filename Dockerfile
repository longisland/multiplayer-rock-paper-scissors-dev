FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src/app.py
ENV FLASK_ENV=production
ENV HOST=0.0.0.0
ENV PORT=5000

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "-m", "src.app"]