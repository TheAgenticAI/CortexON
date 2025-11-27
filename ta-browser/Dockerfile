FROM python:3.11-slim-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install uv
RUN uv pip install -r requirements.txt --system

RUN playwright install chromium
RUN playwright install-deps

COPY . .

CMD ["uvicorn", "core.server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "10"]

