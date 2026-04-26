FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3-pip \
      ffmpeg git curl ca-certificates \
      libgl1 libglib2.0-0 libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m venv /opt/venv && pip install --upgrade pip

WORKDIR /app

COPY pyproject.toml ./
RUN pip install torch==2.3.* --index-url https://download.pytorch.org/whl/cu121 && \
    pip install -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
