FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src ./src
COPY deploy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir --no-deps . && useradd --create-home mcp && mkdir /data && chown mcp:mcp /data
COPY deploy/start.sh /app/start.sh
USER mcp
ENV ASHTADHYAYI_DATA_DIR=/data PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --start-period=180s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/healthz', timeout=4)"
ENTRYPOINT ["sh", "/app/start.sh"]
