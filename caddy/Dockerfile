FROM caddy:2.11-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare@v0.2.4

FROM caddy:2.11

RUN mkdir -p /config /data \
    && chown -R 1000:1000 /config /data

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

USER 1000:1000
