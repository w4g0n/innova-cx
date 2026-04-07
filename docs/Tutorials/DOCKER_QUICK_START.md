# 🐳 InnovaCX Docker - Quick Start Cheat Sheet

## 🚀 First Time Setup (5 minutes)

```bash
# 1. Install Docker Desktop from docker.com
# 2. Clone the repository
git clone <repository-url>
cd innova-cx

# 3. Start everything
docker-compose up --build

# 4. Test it works
# Open browser: http://localhost:8000
```

---

## 📋 Daily Commands

### Starting Work
```bash
# Start Docker Desktop first, then:
docker-compose up -d          # Start in background
```

### While Working
```bash
docker-compose logs -f        # View live logs
docker ps                     # See running containers
```

### Ending Work
```bash
docker-compose down           # Stop everything
```

---

## 🔧 Common Tasks

### Rebuild After Changes
```bash
# When you change requirements.txt or Dockerfile:
docker-compose up --build
```

### Fresh Start (Reset Everything)
```bash
docker-compose down -v        # ⚠️ Deletes database!
docker-compose up --build
```

### Access Database
```bash
docker exec -it innovacx-db psql -U innovacx_admin -d complaints_db
```

### Access Backend Shell
```bash
docker exec -it innovacx-backend bash
```

---

## 🌐 Important URLs

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | Main API endpoint |
| API Docs | http://localhost:8000/docs | Interactive API documentation |
| Database | localhost:5432 | PostgreSQL connection |

---

## 🗄️ Database Connection

```
Host:     localhost
Port:     5432
Database: complaints_db
Username: (see your .env file)
Password: (see your .env file)
```

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Port already in use | Change port in `docker-compose.yml` or stop other program |
| Docker not running | Open Docker Desktop |
| Changes not showing | `docker-compose up --build` |
| Container keeps restarting | Check logs: `docker-compose logs backend` |
| Out of space | `docker system prune -a` |

---

## 📁 Project Structure

```
innova-cx/
├── docker-compose.yml       # Main config file
├── backend/
│   ├── Dockerfile           # Backend image recipe
│   ├── requirements.txt     # Python dependencies
│   └── api/
│       └── main.py          # FastAPI app
└── database/
    └── init.sql             # DB initialization
```

---

## ✨ Key Concepts

**Container** = Isolated environment running your app  
**Image** = Blueprint for creating a container  
**Volume** = Persistent storage (survives restarts)  
**Network** = Allows containers to talk to each other

---

## 💡 Tips

✅ **DO:**
- Use `docker-compose` for everything
- Check logs when debugging: `docker-compose logs -f`
- Rebuild after changing requirements: `docker-compose up --build`

❌ **DON'T:**
- Edit files inside containers (edit on your computer)
- Commit `.env` file to Git
- Use `sudo` with Docker

---

## 🆘 Still Stuck?

1. Check logs: `docker-compose logs -f`
2. See full guide: `DOCKER_GUIDE_FOR_TEAM.pdf`
3. Ask the team
4. Google the error message

---

## 🎯 Quick Test

```bash
# 1. Start containers
docker-compose up -d

# 2. Check they're running
docker ps
# Should see: innovacx-db (healthy) and innovacx-backend

# 3. Test API
curl http://localhost:8000
# Should return: {"message": "InnovaCX API is running!"}

# 4. View logs
docker-compose logs -f backend
```

---

**Your workflow in 4 steps:**
1. `docker-compose up -d` ➜ Start
2. Code normally ➜ Auto-reloads
3. Test at http://localhost:8000
4. `docker-compose down` ➜ Stop

---

*InnovaCX Team | Docker v5.0.0 | January 2026*
