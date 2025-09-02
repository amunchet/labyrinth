# Use Node 16 to match node-sass@6 and Vue CLI 4 era deps
FROM node:16-bullseye

ENV DEBIAN_FRONTEND=noninteractive \
    CHOKIDAR_USEPOLLING=true

# Native build deps (for canvas, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    dos2unix git python3 make g++ \
    libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
  && rm -rf /var/lib/apt/lists/*

# Workdir to match your volume mount
WORKDIR /src

# Entrypoint
ADD entrypoint.sh /entrypoint.sh
RUN dos2unix -n /entrypoint.sh /entrypoint-fixed.sh && chmod +x /entrypoint-fixed.sh

EXPOSE 8000 8080
CMD ["/entrypoint-fixed.sh"]

