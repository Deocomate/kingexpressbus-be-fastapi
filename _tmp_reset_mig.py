from sqlalchemy import create_engine, text
from app.core.config import get_settings

s = get_settings()
e = create_engine(s.database_url.replace("+aiomysql", "+pymysql"))
with e.begin() as c:
    c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for t in ("hotel_bookings", "hotel_rooms", "hotels", "tour_bookings", "tours"):
        c.execute(text(f"DROP TABLE IF EXISTS `{t}`"))
    c.execute(
        text(
            "UPDATE alembic_version SET version_num = '0005_email_verification_tokens'"
        )
    )
    c.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    # Simulate production failed state: hotels+rooms exist, bookings missing
    # Leave clean for full upgrade instead.
print("ok reset")
