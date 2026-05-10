FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies — exclude heavy NLP group (spaCy + fr-core-news-sm)
# not needed at search runtime (only required to rebuild TD1-TD3 indexes)
RUN uv sync --frozen --no-group nlp --no-group dev

# Copy application code and pre-generated indexes
COPY app.py ./
COPY data/ data/
COPY outputs/td3/ outputs/td3/

EXPOSE 8501

# Streamlit config: disable telemetry, bind to all interfaces
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["uv", "run", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]
