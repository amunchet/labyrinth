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
        cron \
        iputils-ping \
	tzdata



COPY requirements.txt /
RUN pip3 install -r /requirements.txt

# Cron installation


ADD entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh


CMD exec /bin/bash -c '/entrypoint-fixed.sh && sleep inf'

