# Works on Hugging Face Spaces (Docker SDK), Koyeb, Railway, or any Docker host.
# HF Spaces: app MUST listen on 7860 -> set PORT=7860 in Space variables.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py Procfile ./
COPY src ./src

CMD ["python", "bot.py"]
