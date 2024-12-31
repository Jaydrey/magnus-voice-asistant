FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y build-essential libpq-dev&& \
    apt-get clean

WORKDIR usr/src/app

COPY ./requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    adduser --disabled-password --no-create-home magnus

ENV PATH="/opt/venv/bin:$PATH"

COPY . .

RUN chown -R magnus:magnus /usr/src/app

USER magnus

EXPOSE 8080

CMD ["fastapi", "dev", "src/main.py"]

