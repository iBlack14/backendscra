# Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium is enough for this scraper)
# We install dependencies for it as well
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Expose port (Easypanel usually maps this automatically)
EXPOSE 8000

# Run the application
# Using uvicorn directly is fine in Docker Linux environment
# But we can use our robust start.py logically, or just direct uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
