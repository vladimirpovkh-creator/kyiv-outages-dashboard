FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 STATE_PATH=/state/status.json
RUN pip install --no-cache-dir telethon==1.45.0 aiohttp==3.13.3
COPY scripts/monitor_forum_prazkyi.py /app/monitor_forum_prazkyi.py
COPY realtime/monitor.py /app/monitor.py
RUN useradd --system --uid 10001 --create-home monitor && mkdir -p /state && chown 10001:10001 /state
USER 10001:10001
EXPOSE 8080
CMD ["python", "/app/monitor.py"]
