"""Database model."""

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from . import app

engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()


class Photo(Base):
    """Photo class."""

    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    username = Column(String(128))
    instagram_id = Column(String(250))
    display_url = Column(String(1024))
    likes = Column(Integer)
    taken_at_timestamp = Column(Integer)


Base.metadata.create_all(engine)
