FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser && mkdir /data && chown appuser:appuser /data
COPY context_me ./context_me
COPY webapp ./webapp
COPY templates ./templates
COPY static ./static
COPY manage.py serve.py ./
USER appuser
ENV CONTEXT_ME_HOSTED=true CONTEXT_ME_DATA_DIR=/data PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "serve.py"]
