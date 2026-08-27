"""Run backend with SQLite for manual testing."""
import os
import uvicorn

os.environ["PDV_ENV_FILE"] = ".env.test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_pdv.db"

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
