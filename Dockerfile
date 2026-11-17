# Heater C advisory (SYNTHETIC SIMULATION unless a signed site config is mounted). Phase 8 package v0.9.
# Build once on a machine with network access (base image + pinned packages). RUN the container with NO outbound network (see docker-compose.yml / INSTALL_SITE.md).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false STREAMLIT_SERVER_HEADLESS=true MODE=SHADOW HEATER_SITE=/app/config/site.yaml

# non-root user with no login shell
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin heater
WORKDIR /app

COPY requirements-runtime.txt .
RUN pip install -r requirements-runtime.txt

COPY --chown=heater:heater app.py ./
COPY --chown=heater:heater src ./src
COPY --chown=heater:heater config ./config
COPY --chown=heater:heater ops ./ops
COPY --chown=heater:heater .streamlit ./.streamlit
COPY --chown=heater:heater tests/conftest.py tests/test_advisory_gate.py ./tests/
# writable mount points for site data (mounted over by docker run / compose)
RUN mkdir -p data reports models incoming && chown -R heater:heater /app && sed -i 's/\r$//' ops/shadow_loop.sh && chmod +x ops/shadow_loop.sh

USER heater
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=3).read()==b'ok' else 1)"
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
