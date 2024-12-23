# requirements.txt
fastapi==0.100.0
sqlalchemy==2.0.19
pydantic==2.1.1
python-jose==3.3.0
passlib==1.7.4
python-multipart==0.0.6
pillow==10.0.0
uvicorn==0.23.1
python-dotenv==1.0.0

# models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    events = relationship("Event", back_populates="creator")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    date = Column(DateTime)
    time = Column(String)
    location = Column(String)
    category = Column(String)
    poster_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator_id = Column(Integer, ForeignKey("users.id"))
    creator = relationship("User", back_populates="events")

class Building(Base):
    __tablename__ = "buildings"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    code = Column(String)
    description = Column(Text)
    location_x = Column(Float)
    location_y = Column(Float)
    type = Column(String)

class Cafe(Base):
    __tablename__ = "cafes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    location = Column(String)
    rating = Column(Float)
    opening_hours = Column(String)
    menu_url = Column(String)

# schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: str
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True

class EventBase(BaseModel):
    title: str
    description: str
    date: datetime
    time: str
    location: str
    category: str

class EventCreate(EventBase):
    poster_url: Optional[str] = None

class Event(EventBase):
    id: int
    created_at: datetime
    creator_id: int
    poster_url: Optional[str]

    class Config:
        from_attributes = True

# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# main.py
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import crud, models, schemas
from database import SessionLocal, engine
from datetime import datetime, timedelta
import os
from PIL import Image
import shutil

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="NUST Navigator API")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication endpoints
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Event endpoints
@app.post("/events/", response_model=schemas.Event)
async def create_event(
    event: schemas.EventCreate,
    poster: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Save poster image
    poster_path = f"static/posters/{datetime.now().timestamp()}_{poster.filename}"
    with open(poster_path, "wb") as buffer:
        shutil.copyfileobj(poster.file, buffer)
    
    # Create event with poster URL
    db_event = crud.create_event(
        db=db,
        event=event,
        creator_id=current_user.id,
        poster_url=poster_path
    )
    return db_event

@app.get("/events/", response_model=List[schemas.Event])
def read_events(
    skip: int = 0,
    limit: int = 100,
    category: str = None,
    db: Session = Depends(get_db)
):
    events = crud.get_events(db, skip=skip, limit=limit, category=category)
    return events

@app.get("/events/{event_id}", response_model=schemas.Event)
def read_event(event_id: int, db: Session = Depends(get_db)):
    event = crud.get_event(db, event_id=event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

# Building endpoints
@app.get("/buildings/", response_model=List[schemas.Building])
def read_buildings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    buildings = crud.get_buildings(db, skip=skip, limit=limit)
    return buildings

@app.get("/buildings/{building_id}", response_model=schemas.Building)
def read_building(building_id: int, db: Session = Depends(get_db)):
    building = crud.get_building(db, building_id=building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return building

# Cafe endpoints
@app.get("/cafes/", response_model=List[schemas.Cafe])
def read_cafes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    cafes = crud.get_cafes(db, skip=skip, limit=limit)
    return cafes

@app.get("/cafes/{cafe_id}", response_model=schemas.Cafe)
def read_cafe(cafe_id: int, db: Session = Depends(get_db)):
    cafe = crud.get_cafe(db, cafe_id=cafe_id)
    if cafe is None:
        raise HTTPException(status_code=404, detail="Cafe not found")
    return cafe
