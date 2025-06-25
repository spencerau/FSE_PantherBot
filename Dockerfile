FROM python:3.12

WORKDIR /app
COPY src/ ./src/
COPY configs/ ./configs/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501

# Set environment variable to indicate we're running in Docker
ENV DOCKER_ENV=true

CMD ["streamlit", "run", "src/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]