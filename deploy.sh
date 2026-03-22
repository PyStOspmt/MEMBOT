#!/bin/bash

# Deployment script for Oracle Cloud Server
# Usage: ./deploy.sh

set -e

echo "🚀 Starting deployment to Oracle Cloud..."

# Check if SSH key exists
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "📝 Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

# Server details
SERVER_IP="138.2.165.238"
SERVER_USER="opc"
PROJECT_NAME="memebot"

echo "🌐 Connecting to server ${SERVER_IP}..."

# Create project directory and setup
ssh ${SERVER_USER}@${SERVER_IP} << 'EOF'
    # Update system
    sudo apt update && sudo apt upgrade -y
    
    # Install Docker
    if ! command -v docker &> /dev/null; then
        echo "🐳 Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
    fi
    
    # Install Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "📦 Installing Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
    
    # Create project directory
    mkdir -p ~/${PROJECT_NAME}
    cd ~/${PROJECT_NAME}
    
    # Create data directory
    mkdir -p data
    
    echo "✅ Server setup complete"
EOF

echo "📤 Copying files to server..."

# Copy files to server
scp -r . ${SERVER_USER}@${SERVER_IP}:~/${PROJECT_NAME}/

echo "🔧 Setting up environment on server..."

ssh ${SERVER_USER}@${SERVER_IP} << EOF
    cd ~/${PROJECT_NAME}
    
    # Copy environment file
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "⚠️  Please edit .env file with your BOT_TOKEN"
    fi
    
    # Build and start the container
    docker-compose down
    docker-compose build
    docker-compose up -d
    
    echo "📊 Container status:"
    docker-compose ps
    
    echo "📋 Logs:"
    docker-compose logs -f memebot
EOF

echo "✅ Deployment complete!"
echo "🔗 Bot should be running on server: ${SERVER_IP}"
echo "📝 Don't forget to:"
echo "   1. SSH into server: ssh ${SERVER_USER}@${SERVER_IP}"
echo "   2. Edit ~/memebot/.env with your BOT_TOKEN"
echo "   3. Restart: cd ~/memebot && docker-compose restart"
