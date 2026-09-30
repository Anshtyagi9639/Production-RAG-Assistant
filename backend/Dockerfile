# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt
# Bake the tokenizer used for chunking into the image so the worker never downloads it at runtime.
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    STORAGE_LOCAL_PATH=/data/uploads

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --no-create-home app \
    && mkdir -p /data/uploads \
    && chown app:app /data/uploads

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/tiktoken /opt/tiktoken
COPY --chown=app:app app ./app

USER app
EXPOSE 8000

# The API. The worker runs the same image with: arq app.workers.settings.WorkerSettings
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
