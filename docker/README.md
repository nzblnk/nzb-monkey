# Dockerfile for nzb-monkey

Run nzb-monkey inside a python alpine based docker container. 

## Build & first run

First create a docker image and an empty config file. Then run a new container with the same user to match file permissions. The config file should be written. Now change the config according to your needs.

```bash
docker build -t nzbmonkey:latest .
touch nzbmonkey.cfg
docker run --rm -it -u $(id -u):$(id -g) -v $PWD/nzbmonkey.cfg:/usr/src/nzbmonkey/nzbmonkey.cfg nzbmonkey:latest 'nzblnk:?t=Our+Sommervacation&h=fbzzreinpngvba&g=a.b.documentaries&p=v4c4t10n4tw1n'
vi nzbmonkey.cfg
```

## Usage (nzblink)

```bash
docker run --rm -it -v $PWD/nzbmonkey.cfg:/usr/src/nzbmonkey/nzbmonkey.cfg nzbmonkey:latest 'nzblnk:?t=Our+Sommervacation&h=fbzzreinpngvba&g=a.b.documentaries&p=v4c4t10n4tw1n'
```

## Usage (parameters)

```bash
docker run --rm -it -v $PWD/nzbmonkey.cfg:/usr/src/nzbmonkey/nzbmonkey.cfg nzbmonkey:latest -t 'Our Sommervacation' -s 'fbzzreinpngvba' -p 'v4c4t10n4tw1n'
```
