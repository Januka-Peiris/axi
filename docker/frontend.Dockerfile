FROM node:20
WORKDIR /app
COPY frontend .
RUN npm install && npm run build
EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host"]
