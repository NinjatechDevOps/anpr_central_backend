"""
Script to create a default super admin organization.
Usage:
    Local:  python scripts/create_admin.py
    Docker: docker exec vehicle-detection-api python scripts/create_admin.py
"""
import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.organization import Organization


ADMIN_NAME = "admin"
ADMIN_CODE = "admin"
ADMIN_PASSWORD = "admin@123"


def generate_token(password: str) -> str:
    """Generate a deterministic 64-char hex token from the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_admin():
    db = SessionLocal()
    try:
        existing = db.query(Organization).filter(Organization.code == ADMIN_CODE).first()
        if existing:
            print(f"Admin organization already exists (id={existing.id}, code='{existing.code}')")
            print(f"Token: {existing.token}")
            return

        admin_org = Organization(
            name=ADMIN_NAME,
            code=ADMIN_CODE,
            description="Default super admin organization",
            token=generate_token(ADMIN_PASSWORD),
            is_super_admin=True,
            is_active=True,
        )
        db.add(admin_org)
        db.commit()
        db.refresh(admin_org)

        print("Super admin organization created successfully!")
        print(f"  Name:     {admin_org.name}")
        print(f"  Code:     {admin_org.code}")
        print(f"  Token:    {admin_org.token}")
        print(f"  Password: {ADMIN_PASSWORD}")
        print()
        print(f"Use this token in the X-API-Token header to authenticate.")
    except Exception as e:
        db.rollback()
        print(f"Error creating admin: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
