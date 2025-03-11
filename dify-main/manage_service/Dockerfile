FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
COPY . .
CMD ["uvicorn", "manage_service:app", "--host", "0.0.0.0", "--port", "8000"]