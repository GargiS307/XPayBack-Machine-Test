from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
from databases import Database
from passlib.context import CryptContext

DATABASE_URL = "postgresql://user:password@localhost/dbname"
POSTGRES_ENGINE = create_engine(DATABASE_URL)
database = Database(DATABASE_URL)

metadata = MetaData()

Base = declarative_base()

# Dependency to get the current database session
def get_db():
    db = POSTGRES_ENGINE.connect()
    try:
        yield db
    finally:
        db.close()

# Define Users table
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    phone = Column(String, unique=True, index=True)

    # Relationship with Profile table
    profile = relationship("Profile", uselist=False, back_populates="user")

# Define Profile table
class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_picture = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

    # Relationship with Users table
    user = relationship("User", back_populates="profile")

# Create tables
Base.metadata.create_all(bind=POSTGRES_ENGINE)

app = FastAPI()

# Dependency to check if email already exists
async def does_email_exist(email: str, db: Session = Depends(get_db)):
    return db.query(User).filter(User.email == email).first()

# Dependency to check if phone already exists
async def does_phone_exist(phone: str, db: Session = Depends(get_db)):
    return db.query(User).filter(User.phone == phone).first()

# Dependency to get the current user from the token
async def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    return db.query(User).filter(User.id == user_id).first()

@app.post("/register/")
async def register_user(
    full_name: str,
    email: str,
    password: str,
    phone: str,
    profile_picture: str,
    db: Session = Depends(get_db)
):
    # Check if the email already exists
    if await does_email_exist(email, db):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if the phone already exists
    if await does_phone_exist(phone, db):
        raise HTTPException(status_code=400, detail="Phone already registered")

    # Hash the password
    hashed_password = get_password_hash(password)

    # Insert user into Users table
    new_user = User(full_name=full_name, email=email, password=hashed_password, phone=phone)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Insert profile picture into Profile table
    new_profile = Profile(profile_picture=profile_picture, user_id=new_user.id)
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    return {
        "user_id": new_user.id,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "profile_picture": profile_picture,
    }

@app.get("/user/{user_id}")
async def get_user_details(user_id: int, db: Session = Depends(get_db)):
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "profile_picture": user.profile.profile_picture,
    }
