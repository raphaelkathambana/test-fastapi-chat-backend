#!/usr/bin/env python3
"""
Seed script to populate database with test vehicles.
Run this after setting up the database and running migrations.
"""
from app.database import SessionLocal
from app.models.models import Vehicle, VehicleStatus
from sqlalchemy.exc import IntegrityError


def seed_vehicles():
    """Add 5 test vehicles to the database."""
    db = SessionLocal()

    test_vehicles = [
        {
            "vin": "1HGBH41JXMN109186",
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
            "status": VehicleStatus.ONLINE_EVALUATION
        },
        {
            "vin": "2HGFG12678H542398",
            "make": "Honda",
            "model": "Accord",
            "year": 2019,
            "status": VehicleStatus.INSPECTION
        },
        {
            "vin": "3FADP4EJ2FM123456",
            "make": "Ford",
            "model": "Mustang",
            "year": 2021,
            "status": VehicleStatus.ONLINE_EVALUATION
        },
        {
            "vin": "5YJSA1E14HF123789",
            "make": "Tesla",
            "model": "Model S",
            "year": 2022,
            "status": VehicleStatus.PENDING
        },
        {
            "vin": "1G1YY22G965123456",
            "make": "Chevrolet",
            "model": "Corvette",
            "year": 2018,
            "status": VehicleStatus.COMPLETED
        }
    ]

    added_count = 0
    skipped_count = 0

    try:
        for vehicle_data in test_vehicles:
            # Check if vehicle already exists
            existing = db.query(Vehicle).filter(Vehicle.vin == vehicle_data["vin"]).first()
            if existing:
                print(f"⚠ Skipped: {vehicle_data['make']} {vehicle_data['model']} (VIN already exists)")
                skipped_count += 1
                continue

            # Create new vehicle
            vehicle = Vehicle(**vehicle_data)
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

            print(f"✓ Added: {vehicle.year} {vehicle.make} {vehicle.model} (ID: {vehicle.id}, VIN: {vehicle.vin})")
            added_count += 1

        print(f"\n{'='*60}")
        print(f"Seed complete! Added {added_count} vehicles, skipped {skipped_count} existing.")
        print(f"{'='*60}")

    except IntegrityError as e:
        db.rollback()
        print(f"✗ Error: Database integrity error - {e}")
    except Exception as e:
        db.rollback()
        print(f"✗ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print(" Seeding Test Vehicles".center(60))
    print("=" * 60)
    print()

    seed_vehicles()
