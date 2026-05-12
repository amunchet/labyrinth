FROM caddy:2.11-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare@v0.2.4

FROM caddy:2.11

RUN apk add --no-cache curl

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
