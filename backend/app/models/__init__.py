"""SQLAlchemy 数据模型"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Boolean, Float, NVARCHAR,
)
from sqlalchemy.orm import relationship
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(NVARCHAR(255), nullable=False)
    original_filename = Column(NVARCHAR(255), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(NVARCHAR(20), nullable=False)  # pdf / docx / txt
    source = Column(NVARCHAR(20), default="upload")        # upload / draft
    file_size = Column(Integer, nullable=False)
    clause_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    reviews = relationship("Review", back_populates="contract", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Contract(id={self.id}, filename='{self.filename}')>"


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    status = Column(NVARCHAR(20), default="pending")  # pending / processing / completed / error
    summary = Column(Text, nullable=True)
    risk_level = Column(NVARCHAR(20), nullable=True)   # high / medium / low
    overall_score = Column(Integer, nullable=True)      # 0-100
    findings_json = Column(Text, nullable=True)         # JSON string for SQL Server compatibility
    token_usage = Column(Integer, nullable=True)
    provider_used = Column(NVARCHAR(50), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    contract = relationship("Contract", back_populates="reviews")
    messages = relationship("Message", back_populates="review", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Review(id={self.id}, contract_id={self.contract_id}, status='{self.status}')>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    role = Column(NVARCHAR(20), nullable=False)         # user / assistant / system
    content = Column(Text, nullable=False)
    anchor_clause_id = Column(NVARCHAR(50), nullable=True)
    anchor_clause_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    review = relationship("Review", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', review_id={self.review_id})>"


class CustomRule(Base):
    __tablename__ = "custom_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(NVARCHAR(255), nullable=False)
    prompt_template = Column(Text, nullable=False)
    category = Column(NVARCHAR(50), default="custom")   # system / custom
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    def __repr__(self):
        return f"<CustomRule(id={self.id}, name='{self.name}', active={self.is_active})>"
