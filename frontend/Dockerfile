FROM node:24-bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json tsconfig.json ./

RUN npm ci

COPY public ./public
COPY src ./src

EXPOSE 3000

CMD ["npm", "run", "dev:frontend"]
