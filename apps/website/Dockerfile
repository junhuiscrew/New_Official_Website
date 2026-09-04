FROM node:24-alpine

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable && corepack prepare pnpm@11.19.0 --activate

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/website/package.json ./apps/website/package.json
COPY apps/admin/package.json ./apps/admin/package.json
COPY packages/config/package.json ./packages/config/package.json
RUN pnpm install --frozen-lockfile

COPY apps/website ./apps/website
COPY packages/config ./packages/config

WORKDIR /workspace/apps/website
RUN pnpm build
EXPOSE 3000

ENV HOST=0.0.0.0
ENV PORT=3000

CMD ["node", ".output/server/index.mjs"]
