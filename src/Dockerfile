FROM python:3.8-slim

COPY requirements.txt ./
COPY dev-requirements.txt ./

RUN apt-get update \
    && apt-get --no-install-recommends --assume-yes install build-essential \
    && apk add postgresql-dev \
    && pip install psycopg2

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /srv

WORKDIR /srv