FROM python:3-alpine

ENV NZBMONKEY_VERSION 0.2.5

WORKDIR /usr/src/
COPY requirements.txt /tmp/
ADD https://github.com/nzblnk/nzb-monkey/releases/download/v$NZBMONKEY_VERSION/nzbmonkey-v$NZBMONKEY_VERSION-linux.tbz2 nzbmonkey.tbz2
ADD https://github.com/nzblnk/nzb-monkey/pull/27/commits/5d255838ed0187bc5c023400d386aba77f296e73.patch fix_nzbking.patch

RUN mkdir -p /usr/src/nzbmonkey && tar --strip 1 -C ./nzbmonkey -xvjf nzbmonkey.tbz2 && rm nzbmonkey.tbz2 && \
    patch -p1 nzbmonkey/nzbmonkey.py fix_nzbking.patch && \
    apk add --no-cache --virtual .build-deps build-base libffi-dev openssl-dev && \
    pip install --no-cache-dir --requirement /tmp/requirements.txt && \
    addgroup -S nzbmonkey && adduser -S -g nzbmonkey nzbmonkey && \
    apk del --no-cache .build-deps

USER nzbmonkey

ENTRYPOINT ["/usr/src/nzbmonkey/nzbmonkey.py"]
CMD ["--help"]
