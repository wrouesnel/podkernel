# This is the last known working version of ROCM for GFX1010
FROM rocm/rocm-terminal:5.1.1

USER root
WORKDIR /root

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
    # Python build requirements
    && apt install -y \
        build-essential \
        libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev liblzma-dev \
    # Run requirements
    && apt install -y \
        nano wget curl \
        python3-virtualenv

ENV PATH="/root/.pyenv/bin:$PATH"
RUN curl https://pyenv.run | bash

RUN pyenv install $(pyenv latest -k 3.8) \
 && pyenv global $(pyenv latest 3.8)

ENV VIRTUAL_ENV=/root/venv
RUN pyenv exec python -m venv ${VIRTUAL_ENV}
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_DIR=/etc/ssl/certs

RUN pip install -U pip

RUN pip install ipykernel ipywidgets

# Install the compatible rocm version
RUN pip install --extra-index-url https://download.pytorch.org/whl/rocm5.1.1 \
    torch==1.12.1+rocm5.1.1 torchvision==0.13.1+rocm5.1.1 torchaudio==0.12.1

# Options for gfx1010 (Navi 10) cards
# ENV HSA_OVERRIDE_GFX_VERSION=10.3.0

# Link amdgpu.ids for ROCm builds
# contributed by https://github.com/Rubonnek
RUN mkdir -p "/opt/amdgpu/share/libdrm" \
 && ln -sf "/usr/share/libdrm/amdgpu.ids" "/opt/amdgpu/share/libdrm/amdgpu.ids"


ENV HOME=/root

COPY ["docker-entrypoint.sh", "/usr/local/bin/docker-entrypoint.sh" ]

ENTRYPOINT [ "docker-entrypoint.sh" ]

CMD [ "-c", "python -m ipykernel_launcher -f $PODKERNEL_CONNECTION_FILE" ]
