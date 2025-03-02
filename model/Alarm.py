from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Alarm(Base):
    __tablename__ = 'alarm'
    ID = Column(Integer, primary_key=True, autoincrement=True)
    AlarmText = Column(String(1000), nullable=False)
    DateTime = Column(DateTime, nullable=False)
    Type = Column(String(10), nullable=True)
