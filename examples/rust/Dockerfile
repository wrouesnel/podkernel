FROM rust

RUN DEBIAN_FRONTEND=noninteractive apt update \
    # Sort out the package dependencies
    && apt download ca-certificates \
    && dpkg --unpack ca-certificates*.deb \
    && rm -vf /var/lib/dpkg/info/ca-certificates.postinst \
              /var/lib/dpkg/info/ca-certificates.triggers \
    && dpkg --configure ca-certificates || true \
    && rm -vf /var/lib/dpkg/info/ca-certificates.postinst \
              /var/lib/dpkg/info/ca-certificates.triggers \
    && dpkg --configure ca-certificates || true \
    && rm -vf /var/lib/dpkg/info/ca-certificates.postinst \
              /var/lib/dpkg/info/ca-certificates.triggers \
    || dpkg --configure ca-certificates \
    && apt install -y -f \
    # Upgrade the environment
    && apt dist-upgrade -y \
    && apt install -y \
        build-essential \
        cmake

RUN cargo install evcxr_jupyter

COPY ["docker-entrypoint.sh", "/usr/local/bin/docker-entrypoint.sh" ]
ENTRYPOINT [ "docker-entrypoint.sh" ]

CMD [ "-c", "evcxr_jupyter --control_file $PODKERNEL_CONNECTION_FILE" ]
