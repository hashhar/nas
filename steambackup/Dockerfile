FROM debian:latest

ARG VERSION

ARG DOWNLOAD_URL="https://www.7-zip.org/a/7z${VERSION}-linux-x64.tar.xz"

RUN apt-get update \
  && apt-get install -y curl tar xz \
  && rm -rf /var/lib/apt/lists/* \
  && curl -fLO "${DOWNLOAD_URL}" \
  && mkdir -p /opt/7z \
  && tar -C /opt/7z -xvf 7z${VERSION}-linux-x64.tar.xz \
  && rm 7z${VERSION}-linux-x64.tar.xz

COPY entrypoint.sh /
ENTRYPOINT [ "/entrypoint.sh" ]
