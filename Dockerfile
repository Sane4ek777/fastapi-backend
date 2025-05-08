# Использование официального образа Node.js
FROM node:20 AS build

# Установка рабочего каталога
WORKDIR /app

# Копирование зависимостей
COPY package.json ./ 
COPY package-lock.json ./ 

# Установка зависимостей
RUN npm install

# Копирование исходного кода
COPY ./ ./

# Сборка проекта
RUN npm run build

# Использование Nginx для сервировки статики
FROM nginx:alpine

COPY ./nginx/default.conf /etc/nginx/conf.d/default.conf
# Копирование собранного фронтенда в папку Nginx
COPY --from=build /app/build /usr/share/nginx/html

# Открытие порта 80 для Nginx
EXPOSE 80
