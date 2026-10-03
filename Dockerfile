FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TELECOM_DATA_DIR=/tmp/telecom-data
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home app
COPY pyproject.toml config.json ./
COPY src ./src
COPY web ./web
RUN pip install --no-deps . && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "telecom_cloud.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
