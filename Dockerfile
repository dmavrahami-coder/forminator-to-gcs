# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# התקן תלויות מערכת
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# העתק קובץ דרישות
COPY requirements.txt .

# התקן תלויות Python
RUN pip install --no-cache-dir -r requirements.txt

# העתק את הקוד
COPY . .

# הגדר משתני סביבה
ENV PORT=8080
ENV FLASK_ENV=production

# הפעל את האפליקציה
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app.main:app
