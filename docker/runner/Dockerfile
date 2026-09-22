FROM python:3.11.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir \
    ipykernel==6.29.5 \
    nbclient==0.10.2 \
    nbformat==5.10.4 \
    pandas==2.2.3 \
    scikit-learn==1.6.1 \
    && useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin validityci

COPY docker/runner/execute_notebook.py /opt/validityci/execute_notebook.py

USER 10001:10001
WORKDIR /workspace/input
ENTRYPOINT ["python", "/opt/validityci/execute_notebook.py"]
