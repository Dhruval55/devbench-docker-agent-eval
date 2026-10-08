FROM python:3.12-slim
WORKDIR /workspace
COPY task.md /workspace/task.md
RUN mkdir -p /etc/nginx && printf 'events {}\nhttp {\n  upstream app_backend { server 127.0.0.1:9000; }\n  server {\n    listen 8080;\n    location /api/ {\n      proxy_pass http://app_backend\n    }\n  }\n}\n' > /etc/nginx/nginx.conf

