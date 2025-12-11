FROM python:3.11-slim
WORKDIR /app
COPY backend .
RUN pip install -e .
EXPOSE 8000
CMD ["axi-api"]
