FROM python:3.12-slim
WORKDIR /workspace
COPY task.md /workspace/task.md
RUN mkdir -p migrations && printf 'PRAGMA foreign_keys = ON;\nCREATE TABLE orders (\n  id INTEGER PRIMARY KEY,\n  customer_id INTEGER NOT NULL,\n  total_cents INTEGER NOT NULL,\n  FOREIGN KEY (customer_id) REFERENCES customers(id)\n);\nCREATE TABLE customers (\n  id INTEGER PRIMARY KEY,\n  email TEXT NOT NULL UNIQUE\n);\n' > migrations/001_create_schema.sql

