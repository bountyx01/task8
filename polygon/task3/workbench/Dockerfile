FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

RUN useradd --create-home bench \
    && mkdir -p /var/log/workbench \
    && chown bench:bench /var/log/workbench

WORKDIR /opt/workbench

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workbench.py storage.py messages.py config.yaml ./

USER bench

CMD ["python", "workbench.py"]
