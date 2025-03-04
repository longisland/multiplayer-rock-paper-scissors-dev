FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and migrations
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY wsgi.py .
COPY tests/ ./tests/
COPY run_tests.sh .

# Make test script executable
RUN chmod +x run_tests.sh

# Install Chrome and ChromeDriver for Selenium tests
RUN apt-get update && \
    apt-get install -y chromium chromium-driver && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src.app
ENV FLASK_ENV=production
ENV HOST=0.0.0.0
ENV PORT=5000

# Expose port
EXPOSE 5000

# Run the application
WORKDIR /app
CMD ["python", "wsgi.py"]