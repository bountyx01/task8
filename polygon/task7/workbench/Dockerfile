FROM alpine:3.23

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN apk add --no-cache python3 py3-pip \
    && python3 -m venv /opt/venv \
    && mkdir -p /var/log/workbench \
    && chmod 1777 /var/log/workbench

WORKDIR /opt/workbench

COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY workbench.py storage.py messages.py config.yaml ./
COPY templates/ templates/

USER 1000:1000
EXPOSE 8080
CMD ["/opt/venv/bin/waitress-serve", "--listen=0.0.0.0:8080", "workbench:app"]
