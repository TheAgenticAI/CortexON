FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install uv
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    g++ \
    && rm -rf /var/lib/apt/lists/*

RUN export PYTHONPATH=/app
RUN apt-get update -y && apt-get install build-essential -y

# Add the --system flag to uv pip install
RUN uv pip install --system --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]