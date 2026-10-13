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
        curl \
        gnupg \
	tzdata


# influxdata-archive.key GPG Fingerprint: 24C975CBA61A024EE1B631787C3D57159FC2F927
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://repos.influxdata.com/influxdata-archive.key \
        -o /tmp/influxdata-archive.key \
    && actual_fingerprint="$( \
        gpg --batch --show-keys --with-colons /tmp/influxdata-archive.key \
        | awk -F: '$1 == "fpr" { print $10; exit }' \
    )" \
    && echo "InfluxData key fingerprint: ${actual_fingerprint}" \
    && test "${actual_fingerprint}" = "24C975CBA61A024EE1B631787C3D57159FC2F927" \
    && gpg --batch --yes \
        --dearmor \
        --output /etc/apt/keyrings/influxdata-archive.gpg \
        /tmp/influxdata-archive.key \
    && rm /tmp/influxdata-archive.key

RUN echo 'deb [signed-by=/etc/apt/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' \
    > /etc/apt/sources.list.d/influxdata.list

RUN apt update && apt -y install telegraf

COPY requirements.txt /requirements.txt
# requirements.txt is hash-locked (edit requirements.in). Wheels only, except
# python-nmap, which publishes nothing but a source archive. --ignore-installed
# because pip cannot replace Ubuntu's own python3-packaging (via python3-pip).
RUN pip3 install --require-hashes --only-binary=:all: --no-binary=python-nmap \
    --ignore-installed -r /requirements.txt --break-system-packages

COPY entrypoint.sh /
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh


CMD ["/entrypoint-fixed.sh"]
