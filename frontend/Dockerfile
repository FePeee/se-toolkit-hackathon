FROM node:25-bookworm-slim
WORKDIR /app
RUN npm install -g pnpm
COPY package.json .
RUN pnpm install
COPY . .
CMD ["pnpm", "run", "dev", "--", "--host"]