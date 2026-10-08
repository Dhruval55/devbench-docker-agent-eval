FROM python:3.12-slim
WORKDIR /workspace
COPY task.md /workspace/task.md
RUN mkdir -p /var/log /output && printf '2026-01-01T10:00:00Z INFO boot ok\n2026-01-01T10:01:00Z ERROR DB_TIMEOUT request_id=a1\n2026-01-01T10:02:00Z WARN retrying\n2026-01-01T10:03:00Z ERROR AUTH_FAILURE request_id=a2\n2026-01-01T10:04:00Z ERROR DB_TIMEOUT request_id=a3\n' > /var/log/app.log

