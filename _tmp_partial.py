from sqlalchemy import create_engine, text
from app.core.config import get_settings

s = get_settings()
e = create_engine(s.database_url.replace("+aiomysql", "+pymysql"))
with e.begin() as b:
    b.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    b.execute(text("DROP TABLE IF EXISTS hotel_bookings"))
    b.execute(text("DROP TABLE IF EXISTS tour_bookings"))
    b.execute(
        text("UPDATE alembic_version SET version_num = '0005_email_verification_tokens'")
    )
    b.execute(text("SET FOREIGN_KEY_CHECKS=1"))
print("partial ok")
