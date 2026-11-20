FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv ca-certificates && rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/scan && /opt/scan/bin/pip install --no-cache-dir bandit==1.9.4
LABEL scan.version="1.9.4" scan.rules="built-in"
ENV PATH=/opt/scan/bin:$PATH HOME=/tmp PYTHONDONTWRITEBYTECODE=1
WORKDIR /src
ENTRYPOINT ["bandit", "-r", "-f", "json", "-o", "/out/bandit.json"]
CMD ["."]
