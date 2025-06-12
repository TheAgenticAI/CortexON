FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set labels
LABEL maintainer="CortexON Team"
LABEL description="Multi-language execution environment for CortexON"

# Install common dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    wget \
    git \
    gnupg \
    software-properties-common \
    unzip \
    vim \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Set up language directories
RUN mkdir -p /environments/python \
    /environments/java \
    /environments/cpp \
    /environments/javascript \
    /environments/typescript \
    /environments/ruby \
    /environments/go \
    /environments/rust \
    /environments/php

# Python setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && pip3 install --no-cache-dir numpy pandas matplotlib \
    && rm -rf /var/lib/apt/lists/*

# Java setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# C++ setup - already included in build-essential

# JavaScript/TypeScript setup
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g typescript axios \
    && rm -rf /var/lib/apt/lists/*

# Ruby setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    ruby-full \
    && gem install bundler \
    && rm -rf /var/lib/apt/lists/*

# Go setup
RUN wget https://golang.org/dl/go1.20.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.20.linux-amd64.tar.gz \
    && rm go1.20.linux-amd64.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

# Rust setup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . "$HOME/.cargo/env" \
    && rustup component add rustfmt
ENV PATH="/root/.cargo/bin:${PATH}"

# PHP setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    php-cli \
    && rm -rf /var/lib/apt/lists/*

# Create language-specific work directories
RUN mkdir -p /app/python \
    /app/java \
    /app/cpp \
    /app/javascript \
    /app/typescript \
    /app/ruby \
    /app/go \
    /app/rust \
    /app/php

# Create activation scripts for different language environments
COPY setup/*.sh /setup/
RUN chmod +x /setup/*.sh

# Set working directory
WORKDIR /app

# Set up environment selection script
RUN echo '#!/bin/bash\n\
case "$1" in\n\
    python) source /setup/activate_python.sh ;;\n\
    java) source /setup/activate_java.sh ;;\n\
    cpp) source /setup/activate_cpp.sh ;;\n\
    javascript) source /setup/activate_javascript.sh ;;\n\
    typescript) source /setup/activate_typescript.sh ;;\n\
    ruby) source /setup/activate_ruby.sh ;;\n\
    go) source /setup/activate_go.sh ;;\n\
    rust) source /setup/activate_rust.sh ;;\n\
    php) source /setup/activate_php.sh ;;\n\
    *) echo "Unknown language: $1" ;;\n\
esac\n\
' > /usr/local/bin/use_env && \
    chmod +x /usr/local/bin/use_env

CMD ["tail", "-f", "/dev/null"]