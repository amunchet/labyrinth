FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive
RUN apt update && \
	apt -y install \ 
		npm \
		dos2unix


RUN npm install -g npm@latest

RUN npm cache clean -f
RUN npm install -g vue
RUN npm install -g @vue/cli 

ADD entrypoint.sh /

RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh
RUN chmod a+x /entrypoint-fixed.sh

CMD exec /bin/bash -c '/entrypoint-fixed.sh && sleep inf'
