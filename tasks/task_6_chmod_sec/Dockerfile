FROM python:3.12-slim
WORKDIR /workspace
COPY task.md /workspace/task.md
RUN mkdir -p /home/agent/.ssh && printf 'PRIVATE KEY\n' > /home/agent/.ssh/id_rsa && printf 'Host *\n  StrictHostKeyChecking no\n' > /home/agent/.ssh/config && chmod 777 /home/agent/.ssh /home/agent/.ssh/id_rsa /home/agent/.ssh/config

