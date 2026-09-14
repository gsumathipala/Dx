# syntax=docker/dockerfile:1
# The instrument server uses only the standard library, so this stays minimal.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

RUN useradd --create-home --uid 1000 dx && chown -R dx:dx /app
USER dx

EXPOSE 5150

CMD ["python", "-m", "dx_instrument.cli"]
