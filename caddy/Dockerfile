FROM caddy:2.11-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare@v0.2.4

FROM caddy:2.11

ARG CADDY_UID=1000
ARG CADDY_GID=1000

RUN mkdir -p /config/caddy /data/caddy \
    && chown -R ${CADDY_UID}:${CADDY_GID} /config/caddy /data/caddy

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

USER ${CADDY_UID}:${CADDY_GID}
