# The image every commit was labeled in.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

# The original source at the pinned commit, so each patch can be applied and
# compared in memory. Fetched from sqlglot's own repository at that commit.
RUN python -c "import io,tarfile,urllib.request; \
u='https://github.com/tobymao/sqlglot/archive/eb11aec4be8cb2122afe713a4816662c3f0fb2fa.tar.gz'; \
t=tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen(u, timeout=120).read())); \
t.extractall('/opt', filter='data')" \
 && mv /opt/sqlglot-eb11aec4be8cb2122afe713a4816662c3f0fb2fa /opt/sqlglot \
 && (python -m compileall -q /opt/sqlglot/sqlglot /opt/sqlglot/tests || true) \
 && chmod -R a+rX /opt/sqlglot

COPY selector.py map.json.gz /app/
# Index where each class or module setting is read, from the original source.
RUN SQLGLOT_SRC=/opt/sqlglot python /app/selector.py --index /app/index.json.gz && chmod -R a+rX /app
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-X", "frozen_modules=on", "/app/selector.py"]
