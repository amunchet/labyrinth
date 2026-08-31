FROM golang:1.23-alpine AS builder

WORKDIR /src

# Dependencies first so edits to the service do not re-download the module
# cache on every rebuild.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/metrics .

FROM alpine:3.20

ARG TZ
ENV TZ=${TZ}

# wget backs the compose healthcheck; tzdata keeps log timestamps aligned with
# the rest of the stack.
RUN apk add --no-cache ca-certificates tzdata wget

COPY --from=builder /out/metrics /usr/local/bin/metrics

USER nobody

EXPOSE 9000

ENTRYPOINT ["/usr/local/bin/metrics"]
