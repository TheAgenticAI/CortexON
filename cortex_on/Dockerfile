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

# Set environment variables
ENV PYTHONPATH=/app
ENV ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ENV ANTHROPIC_MODEL_NAME=${ANTHROPIC_MODEL_NAME:-claude-3-sonnet-20240229}

EXPOSE 8081

# Run both the MCP server and the main API
CMD ["sh", "-c", "python -m agents.mcp_server & uvicorn main:app --host 0.0.0.0 --port 8081"]