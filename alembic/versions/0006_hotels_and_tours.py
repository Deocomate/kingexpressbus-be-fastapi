"""Hotels, rooms, hotel bookings, tours, tour bookings.

Revision ID: 0006_hotels_and_tours
Revises: 0005_email_verification_tokens

FK note: legacy DBs may have `users.id` as BIGINT UNSIGNED (Laravel) or
signed BIGINT (SQLAlchemy create_all). Detect at runtime so user_id matches.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import mysql

revision = "0006_hotels_and_tours"
down_revision = "0005_email_verification_tokens"
branch_labels = None
depends_on = None

# Own PKs / money columns — unsigned is fine when not FK'd to users.
UBIGINT = mysql.BIGINT(unsigned=True)


def _users_id_type(bind) -> sa.types.TypeEngine:
    """Match users.id signedness so FK hotel_bookings.user_id / tour_bookings.user_id work."""
    col_type = bind.execute(
        text(
            "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'users' AND COLUMN_NAME = 'id'"
        )
    ).scalar()
    if col_type and "unsigned" in str(col_type).lower():
        return mysql.BIGINT(unsigned=True)
    return mysql.BIGINT()


def _table_id_type(bind, table_name: str) -> sa.types.TypeEngine:
    """Match an existing table's id signedness (for partial failed upgrades)."""
    col_type = bind.execute(
        text(
            "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            f"AND TABLE_NAME = :t AND COLUMN_NAME = 'id'"
        ),
        {"t": table_name},
    ).scalar()
    if col_type and "unsigned" in str(col_type).lower():
        return mysql.BIGINT(unsigned=True)
    return mysql.BIGINT()


def _drop_incomplete_hotel_stack(bind, tables: set[str]) -> set[str]:
    """If hotel_bookings never got created, drop orphan hotel tables and recreate."""
    if "hotel_bookings" in tables:
        return tables
    orphans = [t for t in ("hotel_rooms", "hotels") if t in tables]
    if not orphans:
        return tables
    bind.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        for name in orphans:
            op.drop_table(name)
    finally:
        bind.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    return set(inspect(bind).get_table_names())


def _drop_incomplete_tour_stack(bind, tables: set[str]) -> set[str]:
    if "tour_bookings" in tables:
        return tables
    if "tours" not in tables:
        return tables
    bind.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        op.drop_table("tours")
    finally:
        bind.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    return set(inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    tables = _drop_incomplete_hotel_stack(bind, tables)
    tables = _drop_incomplete_tour_stack(bind, tables)

    user_id_type = _users_id_type(bind)

    if "hotels" not in tables:
        op.create_table(
            "hotels",
            sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("address", sa.String(length=1000), nullable=True),
            sa.Column("short_description", sa.String(length=1000), nullable=True),
            sa.Column("description", mysql.LONGTEXT(), nullable=True),
            sa.Column("amenities", mysql.JSON(), nullable=True),
            sa.Column("policies", mysql.JSON(), nullable=True),
            sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
            sa.Column("image_list_url", mysql.JSON(), nullable=True),
            sa.Column("map_embedded", mysql.LONGTEXT(), nullable=True),
            sa.Column("check_in_from", sa.String(length=16), nullable=True),
            sa.Column("check_in_to", sa.String(length=16), nullable=True),
            sa.Column("check_out_from", sa.String(length=16), nullable=True),
            sa.Column("check_out_to", sa.String(length=16), nullable=True),
            sa.Column("rating_score", sa.String(length=16), nullable=True),
            sa.Column("rating_label", sa.String(length=255), nullable=True),
            sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
        op.create_index("ix_hotels_slug", "hotels", ["slug"])
        tables.add("hotels")

    hotel_id_type = _table_id_type(bind, "hotels") if "hotels" in tables else UBIGINT

    if "hotel_rooms" not in tables:
        op.create_table(
            "hotel_rooms",
            sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
            sa.Column("hotel_id", hotel_id_type, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("capacity_adults", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("bed_label", sa.String(length=255), nullable=True),
            sa.Column("size_m2", sa.Integer(), nullable=True),
            sa.Column("amenities", mysql.JSON(), nullable=True),
            sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
            sa.Column("image_list_url", mysql.JSON(), nullable=True),
            sa.Column("base_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("sale_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("breakfast_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("cancel_fee_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inventory_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_hotel_rooms_hotel_id", "hotel_rooms", ["hotel_id"])
        op.create_index("ix_hotel_rooms_slug", "hotel_rooms", ["slug"])
        tables.add("hotel_rooms")

    room_id_type = _table_id_type(bind, "hotel_rooms") if "hotel_rooms" in tables else UBIGINT
    hotel_id_type = _table_id_type(bind, "hotels")

    if "hotel_bookings" not in tables:
        op.create_table(
            "hotel_bookings",
            sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
            sa.Column("booking_code", sa.String(length=64), nullable=False),
            sa.Column("user_id", user_id_type, nullable=True),
            sa.Column("hotel_id", hotel_id_type, nullable=False),
            sa.Column("room_id", room_id_type, nullable=False),
            sa.Column("check_in", sa.Date(), nullable=False),
            sa.Column("check_out", sa.Date(), nullable=False),
            sa.Column("nights", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("rooms_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("adults", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("children", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("breakfast_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("breakfast_unit_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("total_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("customer_name", sa.String(length=255), nullable=False),
            sa.Column("customer_email", sa.String(length=255), nullable=True),
            sa.Column("customer_phone", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("payment_method", sa.String(length=64), nullable=False, server_default="cash_at_property"),
            sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="unpaid"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("hotel_name_snapshot", sa.String(length=255), nullable=True),
            sa.Column("room_name_snapshot", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["room_id"], ["hotel_rooms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("booking_code"),
        )
        op.create_index("ix_hotel_bookings_booking_code", "hotel_bookings", ["booking_code"])
        op.create_index("ix_hotel_bookings_hotel_id", "hotel_bookings", ["hotel_id"])
        op.create_index("ix_hotel_bookings_room_id", "hotel_bookings", ["room_id"])

    if "tours" not in tables:
        op.create_table(
            "tours",
            sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("short_description", sa.String(length=1000), nullable=True),
            sa.Column("description", mysql.LONGTEXT(), nullable=True),
            sa.Column("itinerary", mysql.LONGTEXT(), nullable=True),
            sa.Column("duration_label", sa.String(length=255), nullable=True),
            sa.Column("duration_hours", sa.Integer(), nullable=True),
            sa.Column("base_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("max_guests", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("highlights", mysql.JSON(), nullable=True),
            sa.Column("includes", mysql.JSON(), nullable=True),
            sa.Column("excludes", mysql.JSON(), nullable=True),
            sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
            sa.Column("image_list_url", mysql.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
        op.create_index("ix_tours_slug", "tours", ["slug"])
        tables.add("tours")

    tour_id_type = _table_id_type(bind, "tours") if "tours" in set(inspect(bind).get_table_names()) else UBIGINT

    if "tour_bookings" not in set(inspect(bind).get_table_names()):
        op.create_table(
            "tour_bookings",
            sa.Column("id", UBIGINT, autoincrement=True, nullable=False),
            sa.Column("booking_code", sa.String(length=64), nullable=False),
            sa.Column("user_id", user_id_type, nullable=True),
            sa.Column("tour_id", tour_id_type, nullable=False),
            sa.Column("tour_date", sa.Date(), nullable=False),
            sa.Column("guests", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("unit_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("total_price", UBIGINT, nullable=False, server_default="0"),
            sa.Column("customer_name", sa.String(length=255), nullable=False),
            sa.Column("customer_email", sa.String(length=255), nullable=True),
            sa.Column("customer_phone", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("payment_method", sa.String(length=64), nullable=False, server_default="cash_at_property"),
            sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="unpaid"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("tour_name_snapshot", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("booking_code"),
        )
        op.create_index("ix_tour_bookings_booking_code", "tour_bookings", ["booking_code"])
        op.create_index("ix_tour_bookings_tour_id", "tour_bookings", ["tour_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for name in ("tour_bookings", "tours", "hotel_bookings", "hotel_rooms", "hotels"):
        if name in tables:
            op.drop_table(name)
