FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11

COPY --from=builder /usr/local/bin /usr/local/bin

RUN mkdir -p /var/moongsan/secret && chown 1000:1000 /var/moongsan/secret

COPY app/ ./

EXPOSE 8100

ENTRYPOINT ["bash", "-c", "uvicorn main:app --host 0.0.0.0 --port 8100 --log-level debug --access-log 2>&1 | tee -a /var/moongsan/log/ai_moongsan.log"]
