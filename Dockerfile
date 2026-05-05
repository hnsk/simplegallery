FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SIMPLEGALLERY_SOURCE=/source \
    SIMPLEGALLERY_OUTPUT=/output

RUN apk add --no-cache \
        imagemagick \
        imagemagick-dev \
        libheif \
        libheif-dev \
        libwebp \
        libwebp-dev \
        tiff \
        tiff-dev \
        ffmpeg \
        build-base

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip \
 && pip install -e ".[dev]"

COPY docker/imagemagick-policy.xml /etc/ImageMagick-7/policy.xml

COPY tests ./tests

VOLUME ["/source", "/output"]

ENTRYPOINT ["simplegallery"]
CMD ["--help"]
