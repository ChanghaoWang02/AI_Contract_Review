FROM node:20-alpine

WORKDIR /app

# 安装 pnpm
RUN npm install -g pnpm

# 复制 pnpm 相关文件
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install

COPY . .

EXPOSE 5173

CMD ["pnpm", "run", "dev", "--", "--host", "0.0.0.0"]
