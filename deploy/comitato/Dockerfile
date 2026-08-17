# Immagine dell'app Comitato (ADR 0010). Build context: la RADICE del monorepo.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/camperio/core:/opt/camperio/apps/comitato \
    MPLBACKEND=Agg

RUN pip install --no-cache-dir \
    "Flask>=3.0" "python-docx>=1.1" "openpyxl>=3.1" "reportlab>=4.0" \
    "matplotlib>=3.7" "gunicorn>=21" "oracledb>=2.0"

WORKDIR /opt/camperio
COPY core/ core/
COPY apps/comitato/ apps/comitato/

WORKDIR /opt/camperio/apps/comitato
EXPOSE 5001
# 0.0.0.0 e' corretto QUI: la rete del container e' isolata; verso l'host
# si pubblica solo su loopback (compose) e all'esterno parla solo nginx.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "120", "app:app"]
