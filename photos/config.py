import os
class DevelopmentConfig(object):
    SQLALCHEMY_DATABASE_URI = "postgresql://photos_user@localhost:5432/photos"
    DEBUG = True
    SECRET_KEY = os.environ.get("PHOTOS_SECRET_KEY", os.urandom(12))

class TestingConfig(object):
    SQLALCHEMY_DATABASE_URI = "postgresql://photos_user@localhost:5432/photos-test"
    DEBUG = False
    SECRET_KEY = "Not secret"

class TravisConfig(object):
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost:5432/photos-test"
    DEBUG = False
    SECRET_KEY = "Not secret"
