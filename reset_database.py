#!/usr/bin/env python3
"""
Reset database: Drop all tables and re-run migrations.
WARNING: This will DELETE ALL DATA!
"""
from sqlalchemy import text
from app.database import engine, Base
from alembic import command
from alembic.config import Config
import sys


def drop_all_tables():
    """Drop all tables and types from the database."""
    print("=" * 60)
    print(" Dropping All Tables".center(60))
    print("=" * 60)
    print()

    try:
        with engine.begin() as conn:
            # Drop alembic version table
            print("Dropping alembic version tracking...")
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

            # Drop all tables
            print("Dropping all tables...")
            conn.execute(text("""
                DROP TABLE IF EXISTS notifications CASCADE;
                DROP TABLE IF EXISTS comments CASCADE;
                DROP TABLE IF EXISTS vehicles CASCADE;
                DROP TABLE IF EXISTS messages CASCADE;
                DROP TABLE IF EXISTS users CASCADE;
            """))

            # Drop enum types
            print("Dropping enum types...")
            conn.execute(text("""
                DROP TYPE IF EXISTS vehiclestatus CASCADE;
                DROP TYPE IF EXISTS sectiontype CASCADE;
            """))

            print("\n✓ All tables and types dropped successfully!")
            return True

    except Exception as e:
        print(f"\n✗ Failed to drop tables: {e}")
        return False


def run_migrations():
    """Run all migrations from scratch."""
    print("\n" + "=" * 60)
    print(" Running Migrations".center(60))
    print("=" * 60)
    print()

    try:
        alembic_cfg = Config("alembic.ini")

        print("Running all migrations...")
        command.upgrade(alembic_cfg, "head")

        print("\n✓ All migrations completed successfully!")
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
        from seed_vehicles import seed_vehicles
        seed_vehicles()
        return True

    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print(" DATABASE RESET SCRIPT".center(60))
    print("=" * 60)
    print()
    print("⚠  WARNING: This will DELETE ALL DATA in the database!")
    print()
    print("This script will:")
    print("  1. Drop all tables (users, vehicles, comments, etc.)")
    print("  2. Drop all enum types")
    print("  3. Drop Alembic version tracking")
    print("  4. Run all migrations from scratch")
    print("  5. Seed test data")
    print()

    # Confirm
    confirm = input("Are you sure you want to proceed? (type 'yes' to confirm): ").strip()

    if confirm.lower() != 'yes':
        print("\n✗ Reset cancelled. No changes made.")
        sys.exit(0)

    print()

    # Step 1: Drop everything
    if not drop_all_tables():
        print("\n⚠ Reset incomplete due to errors")
        sys.exit(1)

    # Step 2: Run migrations
    if not run_migrations():
        print("\n⚠ Reset incomplete due to errors")
        sys.exit(1)

    # Step 3: Seed data
    if not seed_data():
        print("\n⚠ Reset incomplete due to errors")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(" Reset Complete!".center(60))
    print("=" * 60)
    print("\nYour database has been reset and is ready to use!")
    print()


if __name__ == "__main__":
    main()
