ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY rootfs /

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-requests

RUN pip3 install -r /etc/services.d/octoprint-filament-manager-mqtt/requirements.txt

