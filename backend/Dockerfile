FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive

ARG TZ
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN   apt-get update && apt-get -y install python3 \
		python3-pip \
		dos2unix \
        libssl-dev \
        nmap \
        openssh-client \
        sshpass \
        git \
        iputils-ping \
        wget \
	tzdata


# influxdata-archive_compat.key GPG Fingerprint: 9D539D90D3328DC7D6C8D3B9D8FF8E1F7DF8B07E
RUN wget -q https://repos.influxdata.com/influxdata-archive_compat.key
RUN echo '393e8779c89ac8d958f81f942f9ad7fb82a25e133faddaf92e15b16e6ac9ce4c influxdata-archive_compat.key' | sha256sum -c && cat influxdata-archive_compat.key | gpg --dearmor | tee /etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg > /dev/null
RUN echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg] https://repos.influxdata.com/debian stable main' | tee /etc/apt/sources.list.d/influxdata.list

RUN apt update && apt -y install telegraf

COPY requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt --break-system-packages

ADD entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh


CMD exec /bin/bash -c '/entrypoint-fixed.sh'

