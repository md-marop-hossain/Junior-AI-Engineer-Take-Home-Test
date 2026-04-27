"""Tools the LangGraph agent can call.

Each tool wraps a database action behind a typed Pydantic interface so the
LLM can call it with validated input.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field, PositiveInt


# Input schemas

class SearchPropertiesInput(BaseModel):
    """Input fields for `search_available_properties`."""

    location: str = Field(..., description="City or area, e.g. \"Cox's Bazar\".")
    check_in: date = Field(..., description="Check-in date (YYYY-MM-DD).")
    check_out: date = Field(..., description="Check-out date (YYYY-MM-DD).")
    guests: PositiveInt = Field(..., description="Number of guests.")


class GetListingDetailsInput(BaseModel):
    """Input fields for `get_listing_details`."""

    listing_id: str = Field(..., description="Internal listing UUID.")


class CreateBookingInput(BaseModel):
    """Input fields for `create_booking`."""

    listing_id: str = Field(..., description="Listing the guest wants to book.")
    guest_name: str = Field(..., description="Full name of the booking guest.")
    guest_phone: str = Field(..., description="Bangladeshi mobile, e.g. '+8801…'.")
    check_in: date
    check_out: date
    guests: PositiveInt
    conversation_id: Optional[str] = Field(
        default=None, description="Originating conversation UUID."
    )


# Tool functions

@tool("search_available_properties", args_schema=SearchPropertiesInput)
def search_available_properties(
    location: str,
    check_in: date,
    check_out: date,
    guests: int,
) -> dict:
    """Find listings in `location` that fit the date range and guest count.

    Returns:
        {"results": [{"listing_id", "title", "price_per_night_bdt",
                      "max_guests", "rating"}], "count": int}
    """
    from sqlalchemy import select, not_
    from db.database import get_session
    from db.models import Booking, Listing

    overlap = (
        select(Booking.booking_id)
        .where(
            Booking.listing_id == Listing.listing_id,
            Booking.check_in < check_out,
            Booking.check_out > check_in,
            Booking.status != "cancelled",
        )
        .exists()
    )

    stmt = (
        select(Listing)
        .where(
            Listing.location.ilike(f"%{location}%"),
            Listing.max_guests >= guests,
            not_(overlap),
        )
        .limit(10)
    )

    with get_session() as session:
        listings = session.scalars(stmt).all()
        results = [
            {
                "listing_id": str(row.listing_id),
                "title": row.title,
                "price_per_night_bdt": row.price_per_night_bdt,
                "max_guests": row.max_guests,
                "rating": float(row.rating) if row.rating is not None else None,
            }
            for row in listings
        ]

    return {"results": results, "count": len(results)}


@tool("get_listing_details", args_schema=GetListingDetailsInput)
def get_listing_details(listing_id: str) -> dict:
    """Return detailed information for a single listing.

    Returns:
        {"listing_id", "title", "description", "address",
         "price_per_night_bdt", "max_guests", "amenities", "photos"}
    """
    import uuid
    from sqlalchemy import select
    from db.database import get_session
    from db.models import Listing

    try:
        lid = uuid.UUID(listing_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid listing ID: {listing_id!r}"}

    stmt = select(Listing).where(Listing.listing_id == lid)

    with get_session() as session:
        row = session.scalars(stmt).first()
        if row is None:
            return {"error": f"listing {listing_id!r} not found"}
        return {
            "listing_id": str(row.listing_id),
            "title": row.title,
            "description": row.description,
            "address": row.address,
            "price_per_night_bdt": row.price_per_night_bdt,
            "max_guests": row.max_guests,
            "amenities": row.amenities or [],
            "photos": row.photos or [],
            "rating": float(row.rating) if row.rating is not None else None,
        }


@tool("create_booking", args_schema=CreateBookingInput)
def create_booking(
    listing_id: str,
    guest_name: str,
    guest_phone: str,
    check_in: date,
    check_out: date,
    guests: int,
    conversation_id: Optional[str] = None,
) -> dict:
    """Create a booking and return the confirmation payload.

    Returns:
        {"booking_id", "status": "confirmed", "total_bdt", "check_in", "check_out"}
    """
    import uuid
    from sqlalchemy import select
    from db.database import get_session
    from db.models import Booking, Listing

    nights = (check_out - check_in).days
    if nights <= 0:
        return {"error": "check_out must be after check_in"}

    try:
        lid = uuid.UUID(listing_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid listing ID: {listing_id!r}"}

    with get_session() as session:
        listing = session.scalars(
            select(Listing).where(Listing.listing_id == lid)
        ).first()

        if listing is None:
            return {"error": f"listing {listing_id!r} not found"}

        total_bdt = listing.price_per_night_bdt * nights
        conv_uuid = uuid.UUID(conversation_id) if conversation_id else None

        booking = Booking(
            listing_id=lid,
            guest_name=guest_name,
            guest_phone=guest_phone,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            total_bdt=total_bdt,
            status="confirmed",
            conversation_id=conv_uuid,
        )
        session.add(booking)
        session.flush()  # get booking_id before commit

        return {
            "booking_id": str(booking.booking_id),
            "status": "confirmed",
            "total_bdt": total_bdt,
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
        }


# Convenience list used for LLM binding and name-based routing.
ALL_TOOLS = [search_available_properties, get_listing_details, create_booking]
