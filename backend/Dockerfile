FROM python:3.11-slim

WORKDIR /app

# Logs Python affiches immediatement dans `docker logs`
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU uniquement (~200 Mo) : sans cela, pip installe la version CUDA
# (~3 Go de librairies NVIDIA inutiles dans ce conteneur sans GPU), ce qui fait
# echouer ou bloquer le build. Couche separee pour profiter du cache Docker.
RUN pip install --no-cache-dir --default-timeout=300 --retries 5 \
    torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=300 --retries 5 -r requirements.txt

COPY . .

RUN mkdir -p data/uploads database

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
