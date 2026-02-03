# innova-cx

how to run project with docker:

docker is now split into profiles so you only run the resources you need
!!! DOCKER COMPOSE UP does not work anymore 

for backend:
docker compose --profile backend up --build

for front end: (this runs vite no need to do npm run dev anymore)
docker compose --profile frontend up --build

for audio transcriber and analysis:
docker compose --profile audio up --build

for chatbot:
docker compose --profile chatbot up --build

note: only add " --build" if its the first time 
