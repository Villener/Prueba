# Pantalla de Baja Gas - se compila con Vite y la sirve nginx ya compilada.
# En dos etapas: Node solo existe para construir, no viaja a la imagen final.

FROM node:20-alpine AS build
WORKDIR /app

# npm ci y no npm install: instala exactamente lo del lock, sin sorpresas de
# version entre tu maquina y el contenedor.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
