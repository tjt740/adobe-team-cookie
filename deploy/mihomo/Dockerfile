# Offline build using the existing application image and the verified official binary.
ARG BASE_IMAGE=adobe-team-cookie:latest
FROM ${BASE_IMAGE}
COPY mihomo /usr/local/bin/mihomo
WORKDIR /config
ENTRYPOINT ["/usr/local/bin/mihomo"]
CMD ["-d", "/config"]
