FROM caddy:2.11-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare@v0.2.4

FROM caddy:2.11

RUN grep -q '^caddy:' /etc/group || addgroup -S caddy \
    && grep -q '^caddy:' /etc/passwd || adduser -S -D -h /var/lib/caddy -s /sbin/nologin -G caddy caddy \
    && chown -R caddy:caddy /config /data

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

USER caddy
