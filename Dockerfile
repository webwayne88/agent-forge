# Dockerfile для Agent Forge
# Минимальный образ: python:3.11-slim
# Запуск: uvicorn app.main:app

FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения и промптов
COPY app/ ./app/
COPY prompts/ ./prompts/

# Проверка импорта приложения (smoke test)
RUN python -c "from app.main import app; print('App imported successfully')"

# Запуск uvicorn на всех интерфейсах (0.0.0.0:8000)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
