"""SQLAlchemy ORM models for the StayEase database."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    price_per_night_bdt: Mapped[int] = mapped_column(Integer, nullable=False)
    max_guests: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amenities: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    photos: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(2, 1))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bookings: Mapped[list["Booking"]] = relationship(back_populates="listing")


class Booking(Base):
    __tablename__ = "bookings"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("listings.listing_id"), nullable=False
    )
    guest_name: Mapped[str] = mapped_column(Text, nullable=False)
    guest_phone: Mapped[str] = mapped_column(Text, nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    guests: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_bdt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="confirmed")
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(pgUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    listing: Mapped["Listing"] = relationship(back_populates="bookings")


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guest_phone: Mapped[Optional[str]] = mapped_column(Text)
    # Stored as [{role, content, created_at}] — serialized LangChain turns.
    messages: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Persisted bits of AgentState that must survive between HTTP turns.
    # Holds: {listing_id, search_criteria}
    agent_state: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
