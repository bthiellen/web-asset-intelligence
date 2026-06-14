# Use official Python lightweight runtime
FROM python:3.12-slim

# Enforce clean Python outputs and prevent bytecode caching
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the active workspace
WORKDIR /app

# Copy the merged requirements specification
COPY requirements.txt ./asset_intel/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r ./asset_intel/requirements.txt

# Copy the application source code into the asset_intel package directory
COPY . ./asset_intel/

# Expose the API port
EXPOSE 8000

# Start Uvicorn serving the Asset Intel application
CMD ["uvicorn", "asset_intel.app:app", "--host", "0.0.0.0", "--port", "8000"]
