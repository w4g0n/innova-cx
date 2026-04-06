# InnovaCX Docker Setup Guide
## A Simple Guide for the Team

---

## Table of Contents
1. [What is Docker?](#what-is-docker)
2. [Why Are We Using Docker?](#why-are-we-using-docker)
3. [What Was Just Set Up?](#what-was-just-set-up)
4. [Getting Started](#getting-started)
5. [Essential Commands](#essential-commands)
6. [Daily Workflow](#daily-workflow)
7. [Troubleshooting](#troubleshooting)
8. [Project Structure](#project-structure)

---

## What is Docker?

### Simple Explanation
Think of Docker like a "shipping container" for your application. Just like how physical shipping containers work the same way on any ship, train, or truck, Docker containers work the same way on any computer.

### The Problem It Solves
**Without Docker:**
- "It works on my machine!" 😫
- Everyone has different versions of Python, PostgreSQL, etc.
- Setting up the project takes hours
- Environment conflicts between projects

**With Docker:**
- Everyone runs the exact same environment ✅
- Setup takes 5 minutes
- No more dependency conflicts
- Works the same on Windows, Mac, and Linux

### Key Concepts

#### 1. **Container**
A lightweight, isolated environment that runs your application.
- Like a mini-computer inside your computer
- Has everything it needs: code, libraries, database
- Starts in seconds
- Isolated from your main system

#### 2. **Image**
The blueprint for creating a container.
- Think of it as a recipe
- Defines what goes inside the container
- Built from a `Dockerfile`

#### 3. **Dockerfile**
A text file with instructions to build an image.
```dockerfile
FROM python:3.11-slim       # Start with Python
COPY . /app                 # Copy your code
RUN pip install -r requirements.txt  # Install dependencies
CMD ["python", "app.py"]    # Run your application
```

#### 4. **docker-compose**
A tool to run multiple containers together.
- In our project: runs PostgreSQL + FastAPI backend together
- Defined in `docker-compose.yml`
- Manages networking between containers

---

## Why Are We Using Docker?

### For InnovaCX Specifically:

1. **Consistency Across 7 Team Members**
   - Everyone gets the same Python version (3.11)
   - Everyone gets the same PostgreSQL version (14)
   - No more "works on my machine" issues

2. **Fast Onboarding**
   - New team member? Just run `docker-compose up`
   - No need to install Python, PostgreSQL, libraries manually
   - Setup time: 5 minutes instead of 2 hours

3. **Required by Our Architecture**
   - Our SDD specifies Docker (FR-15)
   - AWS deployment will use containers
   - Industry standard for microservices

4. **Development Benefits**
   - Your real computer stays clean
   - Can reset environment anytime
   - Easy to test different configurations

---

## What Was Just Set Up?

We created a **containerized development environment** with:

### 1. PostgreSQL Database Container
- **What it does:** Stores all complaint data
- **Version:** PostgreSQL 14 (Alpine Linux - small & fast)
- **Port:** 5432 (accessible from your computer)
- **Data persistence:** Uses Docker volumes (data survives container restarts)

**Connection Details:**
```
Host: localhost
Port: 5432
Database: complaints_db
Username: (see your .env file)
Password: (see your .env file)
```

### 2. FastAPI Backend Container
- **What it does:** Runs our Python API
- **Framework:** FastAPI with Uvicorn
- **Port:** 8000 (accessible at http://localhost:8000)
- **Hot-reload enabled:** Changes to code restart the server automatically

### 3. Docker Network
- **What it does:** Allows containers to talk to each other
- **Name:** innovacx-network
- Backend can reach database using hostname `postgres`

### 4. Project Files Created

```
innova-cx/
├── docker-compose.yml          # Orchestrates all containers
├── backend/
│   ├── Dockerfile              # Backend container recipe
│   ├── requirements.txt        # Python dependencies
│   └── api/
│       └── main.py             # FastAPI application
└── database/
    └── init.sql                # Database initialization script
```

---

## Getting Started

### Prerequisites

1. **Install Docker Desktop**
   - Windows/Mac: https://www.docker.com/products/docker-desktop
   - Linux: `sudo apt-get install docker.io docker-compose`

2. **Verify Installation**
   ```bash
   docker --version
   docker-compose --version
   ```
   You should see version numbers.

### First Time Setup

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd innova-cx
   ```

2. **Start Docker Desktop**
   - Open the Docker Desktop application
   - Wait for it to say "Docker is running"

3. **Start the Containers**
   ```bash
   docker-compose up --build
   ```
   
   **What happens:**
   - Downloads PostgreSQL image (~80MB, one-time)
   - Builds Python backend image
   - Installs all Python dependencies
   - Starts both containers
   - **First time:** 3-5 minutes
   - **After that:** 10-30 seconds

4. **Test It Works**
   - Open browser: http://localhost:8000
   - Should see: `{"message": "InnovaCX API is running!"}`
   - API docs: http://localhost:8000/docs

---

## Essential Commands

### Starting & Stopping

#### Start Containers (Foreground)
```bash
docker-compose up
```
- Shows live logs in terminal
- Press `Ctrl+C` to stop
- Good for: Development, seeing what's happening

#### Start Containers (Background)
```bash
docker-compose up -d
```
- Runs in background (detached mode)
- Terminal is free to use
- Good for: When you want to keep working

#### Stop Containers
```bash
docker-compose down
```
- Stops and removes containers
- Data in volumes is kept
- Network is removed

#### Stop and Delete Everything
```bash
docker-compose down -v
```
- Stops containers
- Deletes volumes (⚠️ DELETES DATABASE DATA!)
- Use when you want a fresh start

### Building & Rebuilding

#### Rebuild After Code Changes
```bash
docker-compose up --build
```
- Rebuilds images before starting
- Use when you change:
  - `Dockerfile`
  - `requirements.txt`
  - Want to ensure latest code

#### Force Rebuild (No Cache)
```bash
docker-compose build --no-cache
```
- Rebuilds from scratch
- Use when having weird caching issues

### Viewing & Debugging

#### View Logs
```bash
# All containers
docker-compose logs -f

# Specific container
docker-compose logs -f backend
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100
```

#### See Running Containers
```bash
docker ps
```
Shows: Container ID, name, status, ports

#### See All Containers (including stopped)
```bash
docker ps -a
```

#### Execute Commands Inside Container
```bash
# Access backend container bash
docker exec -it innovacx-backend bash

# Access PostgreSQL
docker exec -it innovacx-db psql -U innovacx_admin -d complaints_db

# Run a Python command
docker exec -it innovacx-backend python -c "print('Hello')"
```

### Maintenance

#### Remove Stopped Containers
```bash
docker container prune
```

#### Remove Unused Images
```bash
docker image prune
```

#### Remove Everything (⚠️ Nuclear Option)
```bash
docker system prune -a --volumes
```
- Removes all stopped containers
- Removes all unused networks
- Removes all unused images
- Removes all volumes
- ⚠️ Use with caution!

---

## Daily Workflow

### Starting Your Work Day

1. **Open Docker Desktop** (Windows/Mac)
2. **Navigate to project**
   ```bash
   cd path/to/innova-cx
   ```
3. **Start containers**
   ```bash
   docker-compose up -d
   ```
4. **Verify it's running**
   ```bash
   docker ps
   # Should see both containers
   ```

### While Working

#### Your Code Changes Automatically Reload
- Edit files in `backend/api/`
- Save the file
- Backend container detects changes
- Server restarts automatically
- No need to restart Docker!

#### View Logs While Working
```bash
docker-compose logs -f backend
```
Leave this open in a separate terminal window.

### Adding New Python Dependencies

1. **Add to `backend/requirements.txt`**
   ```txt
   transformers==4.37.0
   ```

2. **Rebuild the container**
   ```bash
   docker-compose up --build
   ```

### Testing Database Connection

#### Option 1: From Your Computer
Use any PostgreSQL client:
```
Host: localhost
Port: 5432
Database: complaints_db
Username: (see your .env file)
Password: (see your .env file)
```

#### Option 2: Inside Container
```bash
docker exec -it innovacx-db psql -U innovacx_admin -d complaints_db
```

Then run SQL:
```sql
-- List all tables
\dt

-- Query data
SELECT * FROM health_check;

-- Exit
\q
```

### Ending Your Work Day

#### Option 1: Leave it Running
```bash
# Just close your terminal
# Containers keep running in background
```

#### Option 2: Stop Everything
```bash
docker-compose down
```

---

## Troubleshooting

### "Port is already in use"

**Error:**
```
Error: bind: address already in use
```

**Solution:**
1. Check what's using the port:
   ```bash
   # Windows
   netstat -ano | findstr :8000
   netstat -ano | findstr :5432
   
   # Mac/Linux
   lsof -i :8000
   lsof -i :5432
   ```

2. Stop the other program or change our port in `docker-compose.yml`:
   ```yaml
   ports:
     - "8001:8000"  # Use 8001 instead
   ```

### "Docker daemon is not running"

**Solution:**
- Windows/Mac: Open Docker Desktop
- Linux: `sudo systemctl start docker`

### Containers Keep Restarting

**Check logs:**
```bash
docker-compose logs backend
```

**Common causes:**
1. Syntax error in Python code
2. Missing dependency in requirements.txt
3. Database connection issue

**Solution:**
```bash
# Stop everything
docker-compose down -v

# Rebuild
docker-compose up --build
```

### "Cannot connect to database"

**Check database is running:**
```bash
docker ps
# Should see innovacx-db with status "healthy"
```

**Check connection string:**
```python
# In code, should be:
DATABASE_URL = "postgresql://<POSTGRES_USER>:<POSTGRES_PASSWORD>@postgres:5432/<POSTGRES_DB>"
# Note: Use 'postgres' as host, NOT 'localhost'
```

### Changes Not Showing Up

**Cause:** Docker is caching

**Solution:**
```bash
docker-compose down
docker-compose up --build
```

### "Out of disk space"

**Check Docker disk usage:**
```bash
docker system df
```

**Clean up:**
```bash
# Remove unused containers
docker container prune

# Remove unused images
docker image prune

# Remove everything
docker system prune -a
```

### Container Exits Immediately

**Check logs:**
```bash
docker-compose logs backend
```

**Common issues:**
1. Syntax error in code
2. Missing file
3. Wrong command in Dockerfile

### "Permission denied"

**Linux only:**
```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Logout and login again
```

---

## Project Structure

### Current Structure
```
innova-cx/
├── docker-compose.yml          # Main orchestration file
├── .env                        # Environment variables (DON'T commit!)
├── .gitignore                  # Excludes files from Git
│
├── backend/                    # Backend container
│   ├── Dockerfile              # Backend image recipe
│   ├── requirements.txt        # Python dependencies
│   ├── api/                    # Main API folder
│   │   ├── __init__.py
│   │   └── main.py             # FastAPI entry point
│   ├── services/               # Business logic
│   ├── models/                 # Database models
│   ├── audio-transcriber/      # Whisper service
│   ├── complaint-analyzer/     # Sentiment analysis
│   └── chatbot-service/        # Chatbot logic
│
├── frontend/                   # Frontend (future)
│   └── Dockerfile
│
└── database/                   # Database initialization
    └── init.sql                # Runs on first start
```

### Key Files Explained

#### `docker-compose.yml`
**Purpose:** Defines and orchestrates all containers

**Key sections:**
```yaml
services:           # List of containers to run
  postgres:         # Database container
  backend:          # API container
  
volumes:            # Persistent data storage
  postgres_data:    # Database files survive restarts
  
networks:           # Internal communication
  innovacx-network: # Containers can talk to each other
```

#### `backend/Dockerfile`
**Purpose:** Instructions to build the backend image

**What it does:**
1. Starts with Python 3.11
2. Installs system dependencies (ffmpeg, PostgreSQL client)
3. Copies requirements.txt
4. Installs Python packages
5. Copies application code
6. Exposes port 8000
7. Runs the FastAPI server

#### `backend/requirements.txt`
**Purpose:** Lists all Python dependencies

**Currently includes:**
- FastAPI (web framework)
- Uvicorn (ASGI server)
- psycopg2-binary (PostgreSQL driver)
- SQLAlchemy (ORM)
- Pydantic (data validation)

**To add more:**
1. Add line to file
2. Run `docker-compose up --build`

#### `database/init.sql`
**Purpose:** Runs automatically when database starts for first time

**What it does:**
- Creates initial database structure
- Sets up permissions
- Inserts test data

**Note:** Only runs once! To re-run:
```bash
docker-compose down -v  # Delete volume
docker-compose up       # Fresh start
```

---

## Working on Specific Components

### If You're Working on: AI Models

**Your folder:** `backend/models/`

**What you need to do:**
1. Add your Python files
2. If you need new libraries:
   - Add to `backend/requirements.txt`
   - Run `docker-compose up --build`
3. Your code will auto-reload on save

**Testing your model:**
```bash
# Run Python inside container
docker exec -it innovacx-backend python

# Import your model
from models.sentiment_analysis import analyze
analyze("I'm very frustrated!")
```

### If You're Working on: Audio Transcription

**Your folder:** `backend/audio-transcriber/`

**What you need to do:**
1. Add Whisper to requirements:
   ```txt
   whisper==20231117
   librosa==0.10.1
   webrtcvad==2.0.10
   ```
2. Rebuild: `docker-compose up --build`
3. Test with audio files:
   ```bash
   # Copy test file into container
   docker cp test.mp3 innovacx-backend:/app/test.mp3
   
   # Run transcription
   docker exec -it innovacx-backend python -m audio-transcriber.whisper
   ```

### If You're Working on: Database

**Your folder:** `database/`

**What you need to do:**
1. Edit `init.sql` with your schema
2. Delete old database:
   ```bash
   docker-compose down -v
   ```
3. Start fresh:
   ```bash
   docker-compose up
   ```

**Accessing database:**
```bash
# Command line
docker exec -it innovacx-db psql -U innovacx_admin -d complaints_db

# Or use GUI tools:
# - TablePlus
# - DBeaver
# - pgAdmin
# Connect to: localhost:5432
```

### If You're Working on: API Endpoints

**Your folder:** `backend/api/`

**What you need to do:**
1. Edit `main.py` or create new router files
2. Save file (auto-reloads!)
3. Test at http://localhost:8000/docs

**Example: Adding new endpoint**
```python
# In backend/api/main.py

@app.post("/complaints")
async def create_complaint(complaint: dict):
    # Your logic here
    return {"status": "created", "id": 123}
```

**Test it:**
- Go to http://localhost:8000/docs
- Find your new endpoint
- Click "Try it out"
- Submit test data

### If You're Working on: Chatbot

**Your folder:** `backend/chatbot-service/`

**What you need to do:**
1. Add Rasa or your chatbot framework to requirements.txt
2. Create chatbot logic files
3. Rebuild container
4. Test through API

---

## Tips & Best Practices

### DO ✅

1. **Always use `docker-compose`**
   - Don't run `docker run` manually
   - Let docker-compose manage everything

2. **Commit docker files to Git**
   - docker-compose.yml ✅
   - Dockerfile ✅
   - requirements.txt ✅
   - .env ❌ (keep secrets out of Git!)

3. **Check logs when something breaks**
   ```bash
   docker-compose logs -f
   ```

4. **Rebuild after dependency changes**
   ```bash
   docker-compose up --build
   ```

5. **Use volume mounts for code**
   - Already configured in docker-compose.yml
   - Your code changes are live
   - No need to rebuild for code changes

### DON'T ❌

1. **Don't edit files inside containers**
   - Edit on your computer
   - Changes sync automatically

2. **Don't use `sudo` with Docker**
   - Windows/Mac: Not needed
   - Linux: Add yourself to docker group

3. **Don't commit `.env` file**
   - Contains passwords
   - Use `.env.example` instead

4. **Don't store data in containers**
   - Use volumes (already configured)
   - Containers are disposable

5. **Don't skip `docker-compose down`**
   - Properly stops containers
   - Cleans up networks

---

## Quick Reference Card

### Most Common Commands

```bash
# First time setup
docker-compose up --build

# Start (background)
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose up --build

# Fresh start (delete everything)
docker-compose down -v
docker-compose up --build

# Access database
docker exec -it innovacx-db psql -U innovacx_admin -d complaints_db

# Access backend shell
docker exec -it innovacx-backend bash

# See running containers
docker ps

# Test API
curl http://localhost:8000
# Or visit: http://localhost:8000/docs
```

### Ports You Need to Know

- **8000** - FastAPI Backend
  - http://localhost:8000 - API
  - http://localhost:8000/docs - API Documentation
  
- **5432** - PostgreSQL Database
  - Host: localhost
  - Database: complaints_db
  - User: (see your .env file)
  - Password: (see your .env file)

---

## Questions?

### Ask yourself:

1. **Is Docker running?**
   ```bash
   docker ps
   ```

2. **Are containers healthy?**
   ```bash
   docker-compose ps
   ```

3. **What do the logs say?**
   ```bash
   docker-compose logs -f
   ```

### Still stuck?

1. Check this guide's Troubleshooting section
2. Search the error message on Google
3. Ask the team in our chat
4. Check Docker documentation: https://docs.docker.com

---

## Summary

**What Docker gives us:**
- ✅ Same environment for all 7 team members
- ✅ 5-minute setup for new members
- ✅ No dependency conflicts
- ✅ Easy to reset and start fresh
- ✅ Matches production environment
- ✅ Industry standard

**What you need to remember:**
- `docker-compose up -d` to start
- `docker-compose down` to stop
- `docker-compose logs -f` to debug
- Code changes reload automatically
- Rebuild after dependency changes

**Your workflow:**
1. Start Docker Desktop
2. `docker-compose up -d`
3. Code normally in your favorite editor
4. Save files (auto-reloads)
5. Test at http://localhost:8000
6. Commit to Git when done

---

**Welcome to containerized development! 🐳**

*Last updated: January 2026*
*InnovaCX Team - InnovaAI*
