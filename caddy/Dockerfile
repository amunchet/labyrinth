FROM caddy:2.11-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare@v0.2.4

FROM caddy:2.11

# These defaults can be overridden at build time, e.g.
# `docker build --build-arg CADDY_UID=2000 --build-arg CADDY_GID=2000 ./caddy`.
ARG CADDY_UID=1000
ARG CADDY_GID=1000

# Docker copies these seeded subdirectories into a new named volume on first
# mount, so keeping them owned by the runtime UID/GID makes Caddy writable.
RUN mkdir -p /config/caddy /data/caddy \
    && chown -R ${CADDY_UID}:${CADDY_GID} /config/caddy /data/caddy

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

# Keep low-port binding for HTTPS after switching away from root.
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

USER ${CADDY_UID}:${CADDY_GID}
