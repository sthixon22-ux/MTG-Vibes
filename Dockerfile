FROM python:3.12-slim
WORKDIR /app
COPY server.py analytics.py ./
COPY static ./static
RUN useradd --create-home --uid 10001 mtgvibes && chown -R mtgvibes:mtgvibes /app
USER mtgvibes
ENV BIND_HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "server.py"]
