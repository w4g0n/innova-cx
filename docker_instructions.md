
how to run project with docker and Makefile
docker is now split into profiles so you only run the resources you need
and now it uses make commands to run those profiles
!!! DOCKER COMPOSE UP DOES NOT WORK ANYMORE 



FOR BACKEND:
make backend
runs: docker compose --profile backend up
starts: backend + frontend + database

make backend-build 
runs: docker compose --profile backend up --build



FOR FRONT END: 
Note: (this runs vite no need to do npm run dev anymore)
make frontend
runs: docker compose --profile frontend up
starts: frontend + backend + database

make frontend-build 
runs: docker compose --profile frontend up --build



FOR AUDIO TRANSCRIBER AND ANALYSIS:
make audio
runs: docker compose --profile audio up

make audio-build 
runs: docker compose --profile audio up --build



FOR CHATBOT:
make chatbot 
runs: docker compose --profile chatbot up

make chatbot-build 
runs: docker compose --profile chatbot up --build



FOR DEV:
make dev
runs: docker compose --profile dev up

make dev-build
runs: docker compose --profile dev up --build

Dev profile (single profile that runs everything):
docker compose --profile dev up
docker compose --profile dev up --build

Sentiment model notes:
By default it runs in mock mode.

When you have a real model, copy 
`.env.example` to `.env` and set:
USE_MOCK_MODEL=false
SENTIMENT_MODEL_PATH=/path/to/your/model



note: only add " --build" if its the first time running 

basically you do not have to run docker commands again anymore just Make and the build you want to use 
