FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi 'uvicorn[standard]' python-multipart openpyxl pypdf pydantic

COPY app ./app
COPY seed ./seed

RUN mkdir -p /data
ENV WEEKPLANNING_DB=/data/weekplanning.db
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
