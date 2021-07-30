FROM ubuntu:latest

RUN apt update && apt -y install \
    wget \
    python3 \
    python3-pip \
    dos2unix \
    curl

ADD requirements.txt /
RUN pip3 install -r /requirements.txt

ENV REPO="prometheus/alertmanager"
WORKDIR /tmp

RUN curl --silent "https://api.github.com/repos/$REPO/releases/latest" | \
    grep '"tag_name":' | \
    sed -E 's/.*"([^"]+)".*/\1/' | sed 's/v//g' > /tmp/version && \
    wget https://github.com/prometheus/alertmanager/releases/download/v`cat /tmp/version`/alertmanager-`cat /tmp/version`.linux-amd64.tar.gz

RUN tar vxzf alertmanager*.gz
RUN mv alertmanager*/* /usr/local/bin
ADD entrypoint.sh /

RUN dos2unix /entrypoint.sh
EXPOSE 9093

CMD ["/bin/bash", "/entrypoint.sh"]

