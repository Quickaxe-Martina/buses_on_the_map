FROM python:3.10-slim

WORKDIR /home/app

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

COPY ./server.py ./server.py
COPY ./logging_config.py ./logging_config.py

ENTRYPOINT  python server.py