# innova-cx

how to run project with docker and Makefile
docker is now split into profiles so you only run the resources you need
and now it uses make commands to run those profiles
!!! DOCKER COMPOSE UP DOES NOT WORK ANYMORE 



FOR BACKEND:
Make backend
runs: docker compose --profile backend up

Make backend-build 
runs: docker compose --profile backend up --build



FOR FRONT END: 
Note: (this runs vite no need to do npm run dev anymore)
Make frontend
runs: docker compose --profile frontend up --build

Make frontend-build 
runs: docker compose --profile frontend up --build



FOR AUDIO TRANSCRIBER AND ANALYSIS:
Make audio
runs: docker compose --profile audio up

Make audio-build 
runs: docker compose --profile audio up --build



FOR CHATBOT:
Make chatbot 
runs: docker compose --profile chatbot up

Make chatbot-build 
runs: docker compose --profile chatbot up --build



FOR DEV:
Make dev
runs: docker compose --profile backend --profile frontend up

Make dev-build
runs: docker compose --profile backend --profile frontend up --build



note: only add " --build" if its the first time running 

basically you do not have to run docker commands again anymore just Make and the build you want to use 