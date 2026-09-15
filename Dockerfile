# Placeholder container for the release path (sub-chunk 1.1.5). Serves the built simulator
# and the provenance-tracked content root. Sub-chunk 8.1.2 designs the real buyer image and
# replaces this file. Base images pinned by digest.

FROM node:24-alpine@sha256:50c8e8ca1d27439048670df5883f32d57cf81cff6233222c893fd0d9884cbd81 AS build
ARG VERSION=0.0.0
WORKDIR /src
RUN corepack enable && corepack prepare pnpm@10.32.1 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc tsconfig.base.json ./
COPY packages ./packages
COPY sim ./sim
# .npmrc pins use-node-version for pnpm; inside the image the base Node is the pinned major
RUN sed -i '/^use-node-version=/d' .npmrc && pnpm install --frozen-lockfile
RUN pnpm -r build

FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de
ARG VERSION=0.0.0
LABEL org.opencontainers.image.title="rtl-environments simulator" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/BenShoshanRoee/RTL-nev" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"
COPY --from=build /src/sim/dist /usr/share/nginx/html
COPY content /usr/share/nginx/html/cdn
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ >/dev/null || exit 1
