# Multi-stage build with one shared base and two deploy targets:
#   - server : plain HTTP service (local dev, docker-compose, ECS/App Runner)
#   - lambda : AWS Lambda container image (same code, Lambda runtime client)
#
# Build server:  docker build --target server -t insurance-extractor:server .
# Build lambda:  docker build --target lambda --platform linux/arm64 -t insurance-extractor:lambda .

# ---- base: system deps + python deps + app code (shared by both targets) ----
FROM python:3.12-slim AS base
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src:/app
WORKDIR /app

COPY requirements.txt requirements-lambda.txt ./
RUN pip install --no-cache-dir -r requirements-lambda.txt

COPY src/ ./src/
COPY lambda_handler.py ./

# ---- server: uvicorn HTTP server ----
FROM base AS server
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["uvicorn", "insurance_extractor.api:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- lambda: AWS Lambda container image ----
FROM base AS lambda
RUN pip install --no-cache-dir awslambdaric
ARG TARGETARCH=arm64
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie-${TARGETARCH} /usr/local/bin/aws-lambda-rie
RUN chmod +x /usr/local/bin/aws-lambda-rie
COPY entry.sh /entry.sh
RUN chmod +x /entry.sh
ENTRYPOINT ["/entry.sh"]
CMD ["lambda_handler.handler"]
