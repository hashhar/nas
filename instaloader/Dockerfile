FROM python:3-alpine

ARG DATA_ROOT

RUN mkdir /download
WORKDIR /download

RUN apk add --no-cache su-exec
RUN pip3 install --upgrade --no-cache-dir pip
RUN pip3 install --no-cache-dir instaloader

COPY import_firefox_session.py /import_firefox_session.py
COPY entrypoint.sh /entrypoint.sh
COPY args.txt /args.txt

ENV PUID=1000 PGID=1000 HOME=/var/instaloader

RUN mkdir -p "$HOME/.config/instaloader"

ENTRYPOINT [ "/entrypoint.sh", "instaloader", "+/args.txt" ]
