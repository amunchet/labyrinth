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
        cron \
        iputils-ping \
	tzdata



COPY backend/requirements.txt /
RUN pip3 install -r /requirements.txt --break-system-packages

# Cron installation


ADD cron/entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh

# Cron stays root because it installs system crontabs and also executes
# network-discovery jobs that rely on privileged nmap access.

CMD exec /bin/bash -c '/entrypoint-fixed.sh'
