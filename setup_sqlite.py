"""Setup SQLite for manual testing - creates tables and admin user."""
import asyncio
import sys
import os

os.environ["PDV_ENV_FILE"] = ".env.test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_pdv.db"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.models import User, UserRole
from passlib.hash import argon2


async def setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        result = await db.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": "admin"}
        )
        if not result.first():
            admin = User(
                name="Administrador",
                username="admin",
                hashed_password=argon2.hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.commit()
            print("Admin user created: admin / admin123")
        else:
            print("Admin user already exists")

    print("SQLite database ready at test_pdv.db")


if __name__ == "__main__":
    asyncio.run(setup())
