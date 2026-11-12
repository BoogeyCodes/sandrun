# sandrun web dashboard + REST API
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[web]"

# Runs persist in a SQLite file under /data (mount a volume to keep history).
ENV SANDRUN_DB=/data/sandrun.db
VOLUME ["/data"]
EXPOSE 8000

CMD ["sh", "-c", "sandrun serve --db \"$SANDRUN_DB\" --host 0.0.0.0 --port 8000"]
