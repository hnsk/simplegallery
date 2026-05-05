FROM python:3.12-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MAGICK_HOME=/usr \
    SIMPLEGALLERY_WEB=/web

RUN apk add --no-cache \
        imagemagick \
        libheif \
        libwebp \
        tiff \
        ffmpeg \
 && ln -sf libMagickWand-7.Q16HDRI.so.10 /usr/lib/libMagickWand-7.Q16HDRI.so \
 && ln -sf libMagickCore-7.Q16HDRI.so.10 /usr/lib/libMagickCore-7.Q16HDRI.so

WORKDIR /app

COPY docker/imagemagick-policy.xml /etc/ImageMagick-7/policy.xml

FROM base AS builder

RUN apk add --no-cache \
        imagemagick-dev \
        libheif-dev \
        libwebp-dev \
        tiff-dev \
        build-base

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip \
 && pip install --prefix=/install .

FROM base AS runtime

COPY --from=builder /install /usr/local

VOLUME ["/web"]

ENTRYPOINT ["simplegallery"]
CMD ["--help"]

FROM base AS dev

RUN apk add --no-cache \
        imagemagick-dev \
        libheif-dev \
        libwebp-dev \
        tiff-dev \
        build-base

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip \
 && pip install -e ".[dev]"

COPY tests ./tests

VOLUME ["/web"]

ENTRYPOINT ["simplegallery"]
CMD ["--help"]
