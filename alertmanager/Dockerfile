FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive

ARG TZ
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt update && apt -y install \
    wget \
    python3 \
    python3-pip \
    dos2unix \
    tzdata \
    curl 

COPY requirements.txt /
# Hash-locked (edit requirements.in), wheels only
RUN pip3 install --require-hashes --only-binary=:all: -r /requirements.txt \
    --break-system-packages

ENV REPO="prometheus/alertmanager"
WORKDIR /tmp

# The latest release's tag comes from where github.com/.../releases/latest
# redirects (the unauthenticated GitHub API rate-limits shared CI runners), and
# redirects may only go to https.
RUN version=$(curl -fsSIL --proto '=https' -o /dev/null -w '%{url_effective}' \
        "https://github.com/$REPO/releases/latest" | sed 's|.*/tag/v||') && \
    curl -fsSLO --proto '=https' \
        "https://github.com/$REPO/releases/download/v$version/alertmanager-$version.linux-amd64.tar.gz"

RUN tar vxzf alertmanager*.gz
RUN mv alertmanager*/* /usr/local/bin
COPY entrypoint.sh /

RUN dos2unix /entrypoint.sh
EXPOSE 9093

CMD ["/bin/bash", "/entrypoint.sh"]

