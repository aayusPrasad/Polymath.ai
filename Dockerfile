FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libglx-mesa0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Create directories that would normally be generated at runtime
RUN mkdir -p uploads chroma_db_polymath

EXPOSE 8000

CMD uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000}
