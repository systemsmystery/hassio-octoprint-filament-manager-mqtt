ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY rootfs /

RUN apk add --no-cache \
    python3==3.10.5-r \
    py3-pip==22.1.1-r0 \
    py3-requests==2.27.1-r0 && \
    pip3 install --no-cache-dir \
    -r /etc/services.d/octoprint-filament-manager-mqtt/requirements.txt
