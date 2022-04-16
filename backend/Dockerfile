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
        ansible \
        sshpass \
        git \
        iputils-ping \
	tzdata


RUN wget -qO- https://repos.influxdata.com/influxdb.key | apt-key add -
RUN echo "deb https://repos.influxdata.com/debian focal stable" | tee /etc/apt/sources.list.d/influxdb.list

RUN apt update && apt -y install telegraf

COPY requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt

ADD entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh


CMD exec /bin/bash -c '/entrypoint-fixed.sh && sleep inf'

