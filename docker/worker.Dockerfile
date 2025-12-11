FROM python:3.11-slim
WORKDIR /app
COPY backend .
RUN pip install -e .
CMD ["axi-api"] 
# Stub: Using axi-api as placeholder for worker until implemented
