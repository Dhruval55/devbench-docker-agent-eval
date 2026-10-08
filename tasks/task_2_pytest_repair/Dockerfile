FROM python:3.12-slim
WORKDIR /workspace
COPY task.md /workspace/task.md
RUN mkdir -p src tests && printf 'def nth_item(items, n):\n    return items[n]\n\n\ndef middle(items):\n    return nth_item(items, len(items) // 2)\n' > src/utils.py

