FROM node:18-alpine

WORKDIR /app

COPY package.json yarn.lock* package-lock.json* pnpm-lock.yaml* ./
RUN npm ci

COPY . .

# TCP Port
EXPOSE 6000

CMD ["npm", "start"]
