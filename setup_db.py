#!/usr/bin/env python3
"""
Setup database: run migrations and seed data.
"""
from alembic import command
from alembic.config import Config
import sys
import os


def run_migrations():
    """Run database migrations."""
    print("=" * 60)
    print(" Running Database Migrations".center(60))
    print("=" * 60)
    print()

    try:
        # Load alembic configuration
        alembic_cfg = Config("alembic.ini")

        # Run migrations
        print("Upgrading database to latest version...")
        command.upgrade(alembic_cfg, "head")

        print("\n✓ Migrations completed successfully!")
        return True

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return False


def seed_data():
    """Seed test vehicles."""
    print("\n" + "=" * 60)
    print(" Seeding Test Data".center(60))
    print("=" * 60)
    print()

    try:
        # Import and run seed script
        from seed_vehicles import seed_vehicles
        seed_vehicles()
        return True

    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" Database Setup Script".center(60))
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Run database migrations")
    print("  2. Seed test vehicles")
    print()

    # Run migrations
    if not run_migrations():
        print("\n⚠ Setup incomplete due to migration errors")
        sys.exit(1)

    # Seed data
    if not seed_data():
        print("\n⚠ Setup incomplete due to seeding errors")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(" Setup Complete!".center(60))
    print("=" * 60)
    print("\nYou can now start the server:")
    print("  python -m uvicorn app.main:app --reload")
    print("\nAnd run the client:")
    print("  python dealership_client.py")
    print()
