#!/bin/bash

# Quick start script for FastAPI Chat Backend

set -e

echo "=================================="
echo "FastAPI Chat Backend - Quick Start"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found"

# Check if Docker is installed (optional)
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "✓ Docker found"
    DOCKER_AVAILABLE=true
else
    echo "⚠️  Docker not found (optional for PostgreSQL)"
    DOCKER_AVAILABLE=false
fi

echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created (please update with your settings)"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "=================================="
echo "Setup Complete! 🎉"
echo "=================================="
echo ""

# Offer to start PostgreSQL with Docker
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "Would you like to start PostgreSQL with Docker? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "🐳 Starting PostgreSQL..."
        docker-compose up -d
        echo "✓ PostgreSQL is starting..."
        echo "  Waiting for database to be ready..."
        sleep 5
        echo "✓ Database ready"
    fi
fi

echo ""
echo "📝 Next steps:"
echo ""
echo "1. Start the server:"
echo "   python -m uvicorn app.main:app --reload"
echo ""
echo "2. In another terminal, run the client:"
echo "   python client.py"
echo ""
echo "3. View API docs at:"
echo "   http://localhost:8000/docs"
echo ""
echo "4. Or run the demo:"
echo "   python demo.py"
echo ""
