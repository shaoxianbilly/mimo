FROM python:3.11-slim

# 安装git（升级功能需要）
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8899

CMD ["python", "app.py"]
