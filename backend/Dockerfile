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


# influxdata-archive.key GPG Fingerprint: 24C975CBA61A024EE1B631787C3D57159FC2F927
RUN mkdir -p /etc/apt/keyrings && wget -q https://repos.influxdata.com/influxdata-archive.key
RUN gpg --show-keys --with-fingerprint --with-colons ./influxdata-archive.key 2>&1 | grep -q '^fpr:.*24C975CBA61A024EE1B631787C3D57159FC2F927:$' && cat influxdata-archive.key | gpg --dearmor | tee /etc/apt/keyrings/influxdata-archive.gpg > /dev/null
RUN echo 'deb [signed-by=/etc/apt/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' | tee /etc/apt/sources.list.d/influxdata.list

RUN apt update && apt -y install telegraf

COPY requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt --break-system-packages

ADD entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh

# Backend stays root because network discovery shells out to nmap with scan
# modes that require elevated privileges/capabilities in deployed environments.

CMD exec /bin/bash -c '/entrypoint-fixed.sh'
