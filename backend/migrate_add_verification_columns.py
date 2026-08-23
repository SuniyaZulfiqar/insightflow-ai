
"""One-off script: adds the email verification columns to the users table.
 
Run this from your backend project root (same place you run uvicorn from),
so that `app.config` resolves correctly and picks up your .env file:
 
    python migrate_add_verification_columns.py
"""
 
from sqlalchemy import create_engine, text
 
from app.config import settings
 
STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT false;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code VARCHAR(10);",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code_expires_at TIMESTAMPTZ;",
    "UPDATE users SET is_verified = true WHERE is_verified = false;",
]
 
 
def main():
    engine = create_engine(settings.DATABASE_URL)
 
    with engine.begin() as connection:
        for statement in STATEMENTS:
            print(f"Running: {statement}")
            connection.execute(text(statement))
 
    print("\nDone. 'users' table now has is_verified, verification_code, "
          "verification_code_expires_at, and existing accounts were marked verified.")
 
 
if __name__ == "__main__":
    main()