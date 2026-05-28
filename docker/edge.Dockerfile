FROM python:3.11-slim
WORKDIR /app
COPY edge ./edge
RUN pip install --no-cache-dir numpy opencv-python
WORKDIR /app/edge
CMD ["python", "-u", "model_registry.py"]
