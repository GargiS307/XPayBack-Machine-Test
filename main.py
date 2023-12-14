from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Integer, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from databases import Database
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

DATABASE_URL = "postgresql://user:password@localhost/dbname"
POSTGRES_ENGINE = create_engine(DATABASE_URL)
database = Database(DATABASE_URL)

metadata = MetaData()

Base = declarative_base()

# PostgreSQL User Model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    phone = Column(String)


# MongoDB Connection
MONGO_URL = "mongodb://localhost:27017"
mongo_client = AsyncIOMotorClient(MONGO_URL)
mongo_db = mongo_client["profile_pictures"]

app = FastAPI()

# Dependency to get the current database session
def get_db():
    db = POSTGRES_ENGINE.connect()
    try:
        yield db
    finally:
        db.close()

# Dependency to get the MongoDB collection for profile pictures
async def get_profile_pictures_collection():
    return mongo_db.get_collection("profile_pictures")

# Dependency to get the current user from the token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    query = users.select().where(users.c.email == email)
    user = await database.fetch_one(query)
    if user is None:
        raise credentials_exception

    return user

# Dependency to check if email already exists
async def does_email_exist(email: str, db: Session = Depends(get_db)):
    query = db.query(User).filter(User.email == email)
    return db.query(query.exists()).scalar()

@app.post("/register/")
async def register_user(
    full_name: str,
    email: str,
    password: str,
    phone: str,
    profile_picture: str,
    db: Session = Depends(get_db)
):
    # Check if the email already exists in PostgreSQL
    if await does_email_exist(email, db):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password
    hashed_password = get_password_hash(password)

    # Insert user into PostgreSQL
    new_user = User(full_name=full_name, email=email, password=hashed_password, phone=phone)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Insert profile picture into MongoDB
    profile_pictures_collection = await get_profile_pictures_collection()
    await profile_pictures_collection.insert_one(
        {"user_id": new_user.id, "profile_picture": profile_picture}
    )

    return {"user_id": new_user.id, "full_name": full_name, "email": email, "phone": phone}

if __name__ == "__main__":
    import uvicorn

    Base.metadata.create_all(bind=POSTGRES_ENGINE)
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
