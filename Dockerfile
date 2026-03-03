# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables for Deployment Awareness & Scaling
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0
ENV MODEL_ENDPOINT=http://ollama-service:11434

# Set the working directory in the container
WORKDIR /app

# Copy requirement files (Assuming requirements.txt exists or creating it if not)
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Run the FastAPI server using Uvicorn
CMD uvicorn api_server:app --host 0.0.0.0 --port $PORT --workers 4
