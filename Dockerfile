# frontend/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

# copy project & install via PEP-517 – no requirements.txt needed
COPY pyproject.toml .
COPY src ./src
RUN pip install .

# copy Streamlit config (dark theme)
COPY .streamlit /.streamlit

EXPOSE 8501
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.enableCORS=false"]
