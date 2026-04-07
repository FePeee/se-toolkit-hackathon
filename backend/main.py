from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import and_
from jose import JWTError, jwt
import bcrypt as _bcrypt
from pydantic import BaseModel, EmailStr
from datetime import datetime, date, timedelta
from typing import Optional, List
import random
import string

from database import engine, get_db, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Habit Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "habit-tracker-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------- Pydantic schemas ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserOut(BaseModel):
    id: int
    email: str
    name: str
    telegram_id: Optional[str]
    link_code: Optional[str]
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut

class HabitCreate(BaseModel):
    name: str
    reminder_time: Optional[str] = None  # "08:00"

class HabitOut(BaseModel):
    id: int
    name: str
    reminder_time: Optional[str]
    is_active: bool
    streak: int = 0
    done_today: bool = False
    class Config:
        from_attributes = True

class LinkTelegram(BaseModel):
    code: str
    telegram_id: str


# ---------- Auth helpers ----------

def verify_password(plain, hashed):
    return _bcrypt.checkpw(plain.encode(), hashed.encode())

def hash_password(password):
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
    except (JWTError, ValueError):
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def generate_link_code():
    return ''.join(random.choices(string.digits, k=6))


# ---------- Streak helper ----------

def calculate_streak(habit: models.Habit) -> int:
    completion_dates = sorted(
        {c.date for c in habit.completions}, reverse=True
    )
    if not completion_dates:
        return 0
    streak = 0
    check_date = date.today()
    for d in completion_dates:
        if d == check_date:
            streak += 1
            check_date -= timedelta(days=1)
        elif d == check_date - timedelta(days=1):
            check_date = d
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak


# ---------- Auth routes ----------

@app.patch("/api/user-timezone/{telegram_id}")
def update_timezone(telegram_id: str, data: dict, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.timezone = data.get("timezone", "UTC")
    db.commit()
    return {"message": "Timezone updated", "timezone": user.timezone}

@app.post("/api/register-telegram")
def register_telegram(data: dict, db: Session = Depends(get_db)):
    telegram_id = data.get("telegram_id")
    name = data.get("name")
    timezone = data.get("timezone", "UTC")

    existing = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if existing:
        return {"message": "Already registered", "name": existing.name}

    import secrets
    fake_email = f"tg_{telegram_id}@habittracker.bot"
    fake_password = secrets.token_hex(16)

    user = models.User(
        email=fake_email,
        hashed_password=hash_password(fake_password),
        name=name,
        telegram_id=telegram_id,
        timezone=timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registered", "name": user.name}


@app.get("/api/all-users-habits")
def get_all_users_habits(db: Session = Depends(get_db)):
    users = db.query(models.User).filter(models.User.telegram_id != None).all()
    result = []
    today = date.today()
    for user in users:
        habits = db.query(models.Habit).filter(
            models.Habit.user_id == user.id,
            models.Habit.is_active == True
        ).all()
        for h in habits:
            if not h.reminder_time:
                continue
            done_today = any(c.date == today for c in h.completions)
            result.append({
                "telegram_id": user.telegram_id,
                "timezone": user.timezone,
                "habit_name": h.name,
                "reminder_time": h.reminder_time,
                "done_today": done_today,
            })
    return result


@app.get("/api/all-users-stats")
def get_all_users_stats(db: Session = Depends(get_db)):
    users = db.query(models.User).filter(models.User.telegram_id != None).all()
    result = []
    today = date.today()
    week_start = today - timedelta(days=6)
    for user in users:
        habits = db.query(models.Habit).filter(
            models.Habit.user_id == user.id,
            models.Habit.is_active == True
        ).all()
        habits_data = []
        for h in habits:
            done_today = any(c.date == today for c in h.completions)
            week_done = sum(1 for c in h.completions if week_start <= c.date <= today)
            habits_data.append({
                "id": h.id,
                "name": h.name,
                "streak": calculate_streak(h),
                "done_today": done_today,
                "week_completion": f"{week_done}/7",
            })
        result.append({
            "telegram_id": user.telegram_id,
            "name": user.name,
            "habits": habits_data,
        })
    return result


@app.post("/api/auth/register", response_model=Token)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        email=data.email,
        hashed_password=hash_password(data.password),
        name=data.name,
        link_code=generate_link_code(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.post("/api/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.get("/api/auth/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


# ---------- Telegram linking ----------

@app.post("/api/link-telegram")
def link_telegram(data: LinkTelegram, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.link_code == data.code).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid code")
    if db.query(models.User).filter(models.User.telegram_id == data.telegram_id).first():
        raise HTTPException(status_code=400, detail="Telegram already linked to another account")
    user.telegram_id = data.telegram_id
    user.link_code = None
    db.commit()
    return {"message": "Linked successfully", "name": user.name}

@app.get("/api/user-by-telegram/{telegram_id}")
def get_user_by_telegram(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "name": user.name, "telegram_id": user.telegram_id}


# ---------- Habits routes ----------

@app.get("/api/habits", response_model=List[HabitOut])
def get_habits(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    habits = db.query(models.Habit).filter(
        models.Habit.user_id == current_user.id,
        models.Habit.is_active == True
    ).all()
    result = []
    today = date.today()
    for h in habits:
        done_today = any(c.date == today for c in h.completions)
        result.append(HabitOut(
            id=h.id, name=h.name, reminder_time=h.reminder_time,
            is_active=h.is_active, streak=calculate_streak(h), done_today=done_today
        ))
    return result

@app.post("/api/habits", response_model=HabitOut)
def create_habit(data: HabitCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    habit = models.Habit(user_id=current_user.id, name=data.name, reminder_time=data.reminder_time)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return HabitOut(id=habit.id, name=habit.name, reminder_time=habit.reminder_time, is_active=habit.is_active, streak=0, done_today=False)

@app.delete("/api/habits/{habit_id}")
def delete_habit(habit_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(
        models.Habit.id == habit_id, models.Habit.user_id == current_user.id
    ).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    habit.is_active = False
    db.commit()
    return {"message": "Deleted"}

@app.post("/api/habits/{habit_id}/complete")
def complete_habit(habit_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    habit = db.query(models.Habit).filter(
        models.Habit.id == habit_id, models.Habit.user_id == current_user.id
    ).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    existing = db.query(models.Completion).filter(
        models.Completion.habit_id == habit_id,
        models.Completion.date == today
    ).first()
    if existing:
        return {"message": "Already completed today", "streak": calculate_streak(habit)}
    completion = models.Completion(habit_id=habit_id, date=today)
    db.add(completion)
    db.commit()
    db.refresh(habit)
    return {"message": "Completed!", "streak": calculate_streak(habit)}


# ---------- Stats (for bot and web) ----------

@app.get("/api/stats/{telegram_id}")
def get_stats_by_telegram(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    habits = db.query(models.Habit).filter(
        models.Habit.user_id == user.id, models.Habit.is_active == True
    ).all()
    today = date.today()
    week_start = today - timedelta(days=6)
    result = []
    for h in habits:
        done_today = any(c.date == today for c in h.completions)
        week_done = sum(1 for c in h.completions if week_start <= c.date <= today)
        result.append({
            "id": h.id,
            "name": h.name,
            "streak": calculate_streak(h),
            "done_today": done_today,
            "week_completion": f"{week_done}/7",
        })
    return {"name": user.name, "habits": result}

@app.get("/api/habits-by-telegram/{telegram_id}")
def get_habits_by_telegram(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    habits = db.query(models.Habit).filter(
        models.Habit.user_id == user.id, models.Habit.is_active == True
    ).all()
    today = date.today()
    return [{"id": h.id, "name": h.name, "done_today": any(c.date == today for c in h.completions)} for h in habits]

@app.post("/api/habits-by-telegram-create/{telegram_id}", response_model=HabitOut)
def create_habit_by_telegram(telegram_id: str, data: HabitCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    habit = models.Habit(user_id=user.id, name=data.name, reminder_time=data.reminder_time)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return HabitOut(id=habit.id, name=habit.name, reminder_time=habit.reminder_time, is_active=habit.is_active, streak=0, done_today=False)

@app.post("/api/complete-by-telegram/{telegram_id}/{habit_id}")
def complete_by_telegram(telegram_id: str, habit_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    habit = db.query(models.Habit).filter(
        models.Habit.id == habit_id, models.Habit.user_id == user.id
    ).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    if not db.query(models.Completion).filter(
        models.Completion.habit_id == habit_id, models.Completion.date == today
    ).first():
        db.add(models.Completion(habit_id=habit_id, date=today))
        db.commit()
    db.refresh(habit)
    return {"message": "Done!", "streak": calculate_streak(habit)}