#!/bin/bash

# Test Requirements Installation Script
# Installs all dependencies needed for the sharding system tests

echo "📦 Installing test dependencies..."

# Install Python test dependencies
pip install requests mysql-connector-python

echo "✅ Test dependencies installed successfully!"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "🐳 Docker is running"

# Check if the system is up
if curl -s http://localhost:8006/health > /dev/null 2>&1; then
    echo "✅ Sharding system is already running"
else
    echo "🚀 Starting sharding system..."
    docker compose up --build -d
    
    echo "⏳ Waiting for services to start..."
    sleep 60
    
    if curl -s http://localhost:8006/health > /dev/null 2>&1; then
        echo "✅ Sharding system started successfully"
    else
        echo "❌ Failed to start sharding system"
        exit 1
    fi
fi

echo "🧪 Ready to run tests!"
echo "Run: python tests/test_sharding_system.py"