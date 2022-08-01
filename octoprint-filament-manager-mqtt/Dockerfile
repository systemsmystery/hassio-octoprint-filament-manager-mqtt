ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY rootfs /

RUN apk add --no-cache \
    python3=3.10.5-r1 \
    py3-pip=22.2.1-r0 \
    py3-requests=2.28.1-r0

RUN pip3 install -r /etc/services.d/octoprint-filament-manager-mqtt/requirements.txt --no-cache-dir

