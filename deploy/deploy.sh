#!/bin/bash

# OCR Application Deployment Script for EC2
# Run this script on your EC2 instance

set -e

echo "🚀 Starting OCR Application Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please don't run this script as root. Run as ubuntu user."
    exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
print_status "Installing required packages..."
sudo apt install -y python3.9 python3.9-venv python3-pip nginx git curl

# Install Node.js (for n8n if needed)
print_status "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Create application directory
APP_DIR="/home/ubuntu/OCR"
print_status "Setting up application directory: $APP_DIR"

if [ -d "$APP_DIR" ]; then
    print_warning "Directory $APP_DIR already exists. Backing up..."
    sudo mv "$APP_DIR" "${APP_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
fi

# Clone repository (replace with your actual repo)
print_status "Cloning repository..."
git clone https://github.com/your-username/your-repo.git "$APP_DIR"
cd "$APP_DIR"

# Create virtual environment
print_status "Creating Python virtual environment..."
python3.9 -m venv venv
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up environment variables
print_status "Setting up environment variables..."
if [ ! -f .env ]; then
    cat > .env << EOF
# Database
DATABASE_URL=sqlite:///./reports.db

# S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET=your_bucket_name
AWS_REGION=us-east-1

# Backend URL
BACKEND_URL=http://localhost:8000

# GitHub API (for code version)
GITHUB_TOKEN=your_github_token
GITHUB_USERNAME=your_username
GITHUB_REPO=n8n-workflows-backup
GITHUB_BRANCH=main
EOF
    print_warning "Please edit .env file with your actual credentials!"
fi

# Set up systemd services
print_status "Setting up systemd services..."
sudo cp deploy/backend.service /etc/systemd/system/
sudo cp deploy/frontend.service /etc/systemd/system/

# Configure Nginx
print_status "Configuring Nginx..."
sudo cp deploy/nginx.conf /etc/nginx/sites-available/ocr-app
sudo ln -sf /etc/nginx/sites-available/ocr-app /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Enable and start services
print_status "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable backend frontend
sudo systemctl start backend frontend
sudo systemctl restart nginx

# Check service status
print_status "Checking service status..."
sudo systemctl status backend --no-pager
sudo systemctl status frontend --no-pager
sudo systemctl status nginx --no-pager

# Get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

print_status "Deployment completed! 🎉"
echo ""
echo "Your application should be available at:"
echo "  Frontend: http://$PUBLIC_IP"
echo "  Backend API: http://$PUBLIC_IP/api/"
echo "  Health Check: http://$PUBLIC_IP/health"
echo ""
echo "To check logs:"
echo "  Backend: sudo journalctl -u backend -f"
echo "  Frontend: sudo journalctl -u frontend -f"
echo "  Nginx: sudo journalctl -u nginx -f"
echo ""
print_warning "Don't forget to:"
echo "1. Update .env file with your actual credentials"
echo "2. Configure your domain name in nginx.conf"
echo "3. Set up SSL certificate with Let's Encrypt"
echo "4. Update security groups to allow HTTP/HTTPS traffic"
