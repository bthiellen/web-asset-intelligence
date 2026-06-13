# Use official Python lightweight runtime
FROM python:3.12-slim

# Enforce clean Python outputs and prevent bytecode caching
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the active workspace
WORKDIR /app

# Copy dependency specifications first to leverage build cache
COPY requirements.txt .
COPY asset_intel/requirements.txt ./asset_intel_reqs.txt

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r asset_intel_reqs.txt

# Copy the application source code
COPY . .

# Expose the API port
EXPOSE 8000

# Start Uvicorn serving the Asset Intel application
CMD ["uvicorn", "asset_intel.app:app", "--host", "0.0.0.0", "--port", "8000"]
