FROM python:3.11.6-slim

# Install system dependencies for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables for directories
ENV VIDEO_PROCESS_JOB_DIR=/app/data/video_process_jobs
ENV VIDEO_PROCESS_OUTPUT_DIR=/app/data/video_process_outputs
ENV MODEL_DIR=/app/AI/models

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
