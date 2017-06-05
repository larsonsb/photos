import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Unicode
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from flask.ext.login import UserMixin

from . import app

engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    username = Column(String(128))
    instagram_id = Column(String(250))
    display_url = Column(String(1024))
    likes = Column(Integer)
    taken_at_timestamp = Column(Integer)

Base.metadata.create_all(engine)