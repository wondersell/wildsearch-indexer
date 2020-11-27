FROM python:3.8-slim

COPY src/requirements.txt ./

RUN apt-get update \
    && apt-get --no-install-recommends --assume-yes install build-essential \
    && apt-get --no-install-recommends --assume-yes install postgresql python-psycopg2 libpq-dev python-dev

RUN pip install --no-cache-dir -r requirements.txt

ADD src /srv

WORKDIR /srv