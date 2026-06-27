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

ADD requirements.txt /
RUN pip3 install -r /requirements.txt --break-system-packages

ENV REPO="prometheus/alertmanager"
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --create-home --shell /usr/sbin/nologin appuser && \
    mkdir -p /var/tmp/labyrinth && \
    chown -R appuser:appuser /var/tmp/labyrinth
WORKDIR /var/tmp/labyrinth

RUN curl --silent "https://api.github.com/repos/$REPO/releases/latest" | \
    grep '"tag_name":' | \
    sed -E 's/.*"([^"]+)".*/\1/' | sed 's/v//g' > /var/tmp/labyrinth/version && \
    wget https://github.com/prometheus/alertmanager/releases/download/v`cat /var/tmp/labyrinth/version`/alertmanager-`cat /var/tmp/labyrinth/version`.linux-amd64.tar.gz

RUN tar vxzf alertmanager*.gz
RUN mv alertmanager*/* /usr/local/bin
ADD entrypoint.sh /

RUN dos2unix /entrypoint.sh
EXPOSE 9093
USER appuser

CMD ["/bin/bash", "/entrypoint.sh"]
