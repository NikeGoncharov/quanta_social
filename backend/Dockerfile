# --- build deps ---
FROM python:3.13-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# --- runtime ---
FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv
RUN useradd -u 10001 -m app
WORKDIR /app
COPY . .
# data.db is written by the container user; owning /app avoids "readonly database".
RUN mkdir -p /app/data && chown -R app /app && chmod +x docker-entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
