Step 1
run frontend {
- open a terminal from main directory (innova-cx)
- cd frontend 
- npm run dev 
}

Step 2
for first time only:
docker compose --profile audio up --build
(will take a long time around 5 mins)

then: (everytime)
open dokcer desktop
to run whisper:
open a second terminal from main directory(innova-cx)
docker compose --profile audio up