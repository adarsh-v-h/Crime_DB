# ─── Themis's Domain — container image (optional, for local dev) ──────────────
# Production on Render builds from the Procfile, not this image. This exists so
# contributors can run the app without installing Python locally.
FROM python:3.12-slim

# Keep Python output unbuffered and skip .pyc files in the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first so the layer is cached when only source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project.
COPY . .

EXPOSE 5000

# Gunicorn serves both the API and the (pre-built) frontend, same as Render.
CMD ["gunicorn", "Backend.app:app", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120"]
