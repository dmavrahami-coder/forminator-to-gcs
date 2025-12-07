FROM python:3.9-slim

WORKDIR /app

# התקן תלויות מערכת
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# העתק requirements
COPY requirements.txt .

# התקן תלויות Python
RUN pip install --no-cache-dir -r requirements.txt

# העתק את האפליקציה
COPY . .

# הגדר משתני סביבה
ENV PORT=8080
ENV PYTHONUNBUFFERED=TRUE

# הרץ עם Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "600", "main:app"]
