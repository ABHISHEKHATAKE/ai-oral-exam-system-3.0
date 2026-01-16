#!/bin/bash

# AI Oral Examination System - Local Development Setup

echo "🚀 Setting up AI Oral Examination System locally..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your actual API keys and database URL"
fi

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check if services are running
echo "🔍 Checking service status..."
docker-compose ps

# Test backend health
echo "🏥 Testing backend health..."
curl -f http://localhost:8000/health || echo "❌ Backend health check failed"

# Test frontend
echo "🌐 Testing frontend..."
curl -f http://localhost/health || echo "ℹ️  Frontend may still be building"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📍 Access your application:"
echo "   Frontend: http://localhost"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/api/docs"
echo ""
echo "🛠️  Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop services: docker-compose down"
echo "   Restart: docker-compose restart"
echo ""
echo "⚠️  Remember to set your environment variables in .env file!"</content>
<parameter name="filePath">d:\Assigment(2) - Copy\local-setup.sh