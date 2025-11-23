from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BotApp(Base):
    __tablename__ = "bot_apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    repo_url = Column(String(500), nullable=True)
    code_path = Column(String(500), nullable=False)
    runtime = Column(String(50), default="python", nullable=False)
    start_command = Column(String(500), default="python bot.py", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    env_vars = relationship("BotEnvVar", back_populates="bot", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="bot", cascade="all, delete-orphan")


class BotEnvVar(Base):
    __tablename__ = "bot_env_vars"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_apps.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)

    # Relationship
    bot = relationship("BotApp", back_populates="env_vars")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_apps.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, success, failed
    log = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    bot = relationship("BotApp", back_populates="deployments")
