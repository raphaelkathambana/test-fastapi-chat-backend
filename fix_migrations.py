#!/usr/bin/env python3
"""
Fix database migration issues by checking current state and applying appropriate migrations.
"""
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from app.database import engine
import sys


def check_database_state():
    """Check what tables and types exist in the database."""
    print("=" * 60)
    print(" Checking Database State".center(60))
    print("=" * 60)
    print()

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"Found {len(tables)} tables:")
    for table in tables:
        print(f"  - {table}")

    # Check for enum types
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT typname
            FROM pg_type
            WHERE typtype = 'e'
            ORDER BY typname
        """))
        enum_types = [row[0] for row in result]

    if enum_types:
        print(f"\nFound {len(enum_types)} enum types:")
        for enum_type in enum_types:
            print(f"  - {enum_type}")
    else:
        print("\nNo enum types found")

    return tables, enum_types


def determine_migration_state(tables, enum_types):
    """Determine which migration should be marked as applied."""
    has_users = 'users' in tables
    has_messages = 'messages' in tables
    has_vehicles = 'vehicles' in tables
    has_comments = 'comments' in tables
    has_notifications = 'notifications' in tables
    has_vehicle_enum = 'vehiclestatus' in enum_types
    has_section_enum = 'sectiontype' in enum_types

    print("\n" + "=" * 60)
    print(" Migration State Analysis".center(60))
    print("=" * 60)
    print()

    if has_users and has_messages and not has_vehicles:
        print("✓ Migration 001 appears to be applied (users, messages exist)")
        print("✗ Migration 002 not applied (vehicles, comments, notifications missing)")
        return '001'
    elif has_users and has_messages and has_vehicles and has_comments and has_notifications:
        print("✓ Migration 001 appears to be applied")
        print("✓ Migration 002 appears to be applied (all dealership tables exist)")
        return '002'
    elif has_vehicles and has_vehicle_enum:
        print("⚠ Tables created by Base.metadata.create_all() detected")
        print("  All tables exist but Alembic hasn't tracked migrations")
        return 'both'
    else:
        print("⚠ Unknown database state")
        print("  Recommend: Drop database and start fresh")
        return 'unknown'


def stamp_database(revision):
    """Stamp the database with the given revision."""
    print(f"\nStamping database at revision: {revision}")
    try:
        alembic_cfg = Config("alembic.ini")
        command.stamp(alembic_cfg, revision)
        print(f"✓ Database stamped at revision {revision}")
        return True
    except Exception as e:
        print(f"✗ Failed to stamp database: {e}")
        return False


def run_remaining_migrations():
    """Run any remaining migrations."""
    print("\nRunning remaining migrations...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✓ Migrations completed successfully!")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print(" Database Migration Fix Script".center(60))
    print("=" * 60)
    print()

    # Check current state
    tables, enum_types = check_database_state()
    migration_state = determine_migration_state(tables, enum_types)

    print("\n" + "=" * 60)
    print(" Recommended Action".center(60))
    print("=" * 60)
    print()

    if migration_state == '001':
        print("Need to run migration 002 to add dealership tables")
        print("\nExecuting: alembic upgrade head")
        if run_remaining_migrations():
            print("\n✓ Database is now up to date!")
        else:
            sys.exit(1)

    elif migration_state == '002':
        print("Database is already up to date!")
        print("No migrations needed.")

    elif migration_state == 'both':
        print("All tables exist but Alembic tracking is out of sync.")
        print("\nThis happens when Base.metadata.create_all() was used.")
        print("\nRecommended fix:")
        print("  1. Stamp database at revision 002 (mark migrations as applied)")
        print("  2. Continue with normal migrations in the future")
        print()

        choice = input("Apply fix? (y/n): ").strip().lower()
        if choice == 'y':
            if stamp_database('002'):
                print("\n✓ Database is now properly tracked!")
                print("  Future migrations will work normally.")
            else:
                sys.exit(1)
        else:
            print("\nNo changes made.")

    elif migration_state == 'unknown':
        print("Cannot determine database state.")
        print("\nOptions:")
        print("  1. Drop and recreate database (DESTRUCTIVE)")
        print("  2. Manually inspect database and fix")
        print()
        print("To drop and recreate (Windows PowerShell):")
        print("  docker-compose down -v")
        print("  docker-compose up -d")
        print("  # Wait 10 seconds")
        print("  python setup_db.py")

    print()


if __name__ == "__main__":
    main()
