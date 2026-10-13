FROM telegraf

ENV TZ=America/Chicago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


RUN apt update && apt -y install \
    tzdata \
    openssh-server \
    dos2unix \
    curl \
    gnupg \
    sudo \
    python3

RUN echo "root:test" | chpasswd

COPY entrypoint.sh /
RUN dos2unix /entrypoint.sh



CMD ["/entrypoint.sh"]
