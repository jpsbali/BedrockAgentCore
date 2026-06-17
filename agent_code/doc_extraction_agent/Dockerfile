FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN useradd -m -u 1000 bedrock_agentcore

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1

ENTRYPOINT ["opentelemetry-instrument", "python"]
CMD ["-m", "doc_extraction_agent"]

COPY requirements.txt .
RUN uv pip install -r requirements.txt
RUN uv pip install aws-opentelemetry-distro==0.12.2

USER bedrock_agentcore

COPY --chown=bedrock_agentcore:bedrock_agentcore . .
