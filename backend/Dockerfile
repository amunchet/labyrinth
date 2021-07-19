FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive

RUN   apt-get update && apt-get -y install python3 \
		python3-pip \
		dos2unix \
        libssl-dev \
        nmap \
        openssh-client \
        ansible \
        sshpass \
        git


COPY requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt

ADD entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh


CMD exec /bin/bash -c '/entrypoint-fixed.sh && sleep inf'

