# Habit Tracker — daily streaks, Telegram reminders & AI insights

## Quick Start

### 1. Clone and configure
```bash
cp .env.example .env
# Edit .env and set your BOT_TOKEN
```

### 2. Run with Docker Compose
```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 3. How to use
1. Register at http://localhost:3000
2. Copy your 6-digit link code shown on the dashboard
3. Open your Telegram bot and send: `/start 123456`
4. Add habits via `/add` in bot or on the web dashboard

## Bot Commands
| Command | Description |
|---------|-------------|
| `/start CODE` | Link your account |
| `/add` | Add a new habit |
| `/done` | Mark habits as complete today |
| `/list` | View all habits |
| `/stats` | View streaks and weekly stats |

## Project Structure
```
habit-tracker/
├── backend/        # FastAPI + SQLite
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   └── Dockerfile
├── bot/            # Telegram bot (aiogram 3)
│   ├── main.py
│   └── Dockerfile
├── frontend/       # React + Vite
│   ├── src/
│   └── Dockerfile
└── docker-compose.yml
```

## Development (without Docker)

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Bot
```bash
cd bot
pip install -r requirements.txt
BOT_TOKEN=your_token API_URL=http://localhost:8000 python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
