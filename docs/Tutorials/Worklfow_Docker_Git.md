

Docker + Git workflow
Have GitHub repository and docker already set up
From github desktop
git checkout main
git pull
Open docker :
docker-compose up --build
docker-compose up -d
git checkout -b newbranch
Do your work
When done
git status
git add .
git commit -m “insert explanation of changes here”
git push
Then terminal responsd with:
git push --set-upstream origin your-branch-name
Copy and paste
If you started making changes on main before switching to a new
branch
git status
git stash push
git checkout -b newbranch
git stash pop
Then do your work and when done
git add.
git commit -m “insert explanation of changes here”
git push
Then shut down docker:

docker-compose down
Then close the app
Final step:
## Merging:
Open github
Go to pull requests
Create a pull request:
Main <- yournewbranch
Merge it
If it says auto merge
Merge it
If any issues come up let me know thanks.