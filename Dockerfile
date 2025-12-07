FROM python:3.9-slim

WORKDIR /app

# עדכן pip לראשונה
RUN pip install --upgrade pip

COPY requirements.txt .

# התקן עם גרסאות מדויקות
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

CMD ["python", "main.py"]
