FROM ubuntu:noble

ENV DEBIAN_FRONTEND=noninteractive

# 1. Update and install necessary build tools and C/C++ libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    libssl-dev \
    zlib1g-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libgdbm-dev \
    libdb5.3-dev \
    libbz2-dev \
    libexpat1-dev \
    liblzma-dev \
    tk-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Download, compile, and install Python 3.13.2 from official source
RUN wget https://www.python.org/ftp/python/3.13.2/Python-3.13.2.tgz \
    && tar -xf Python-3.13.2.tgz \
    && cd Python-3.13.2 \
    && ./configure --enable-optimizations \
    && make -j $(nproc) \
    && make altinstall \
    && cd .. \
    && rm -rf Python-3.13.2 Python-3.13.2.tgz \
    && ln -s /usr/local/bin/python3.13 /usr/local/bin/python \
    && ln -s /usr/local/bin/pip3.13 /usr/local/bin/pip

# 3. Upgrade pip and install the mandatory requirements.txt
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt
