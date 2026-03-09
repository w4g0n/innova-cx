

## Before Starting
git checkout main #change branch
git pull #pull recent updates from main
npm install #from frontend to download
git checkout -b NEW BRANCH NAME #create new branch

## WORK

After Finishing the Work
git status #check to see if any changes were made
git add . #adds changes to push
git commit -m “Write a message here” #commits and adds comment for others to see
## DOESN’T ADD TO GIT HUB
If you get this error:
Author identity unknown
*** Please tell me who you are.
## Run
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
to set your account's default identity.
Omit --global to set the identity only in this repository.
fatal: unable to auto-detect email address (got 'Hamad@LAPTOP-
VR6MESEV.(none)')

write this:
git config user.name "Hamad Alaa"

git config user.email "your-email@example.com"
git push #pushes it to the branch on git hub

## Merge
Once we create a NEW branch and we are done with everything and want to merge it
and add it to main follow these steps:
- Open https://github.com/w4g0n/innova-cx/
- Go pull request → New pull request
- For Base: main branch
- For Compare: Choose the branch you want to merge
- An Able to merge in green means no conflict between your branch and another
branch
- Add a description for clarity
- Create pull request