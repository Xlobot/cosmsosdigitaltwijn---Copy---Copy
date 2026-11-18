FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "generator_api.py", "--host", "0.0.0.0", "--port", "8080", "--interval", "1.0"]

