# EC2 Deployment Guide

## Prerequisites
- AWS EC2 instance (Ubuntu 20.04+ recommended)
- Security groups configured for ports 22, 80, 443, 8000, 8501
- Domain name (optional, for SSL)

## Step 1: Launch EC2 Instance
1. Launch Ubuntu 20.04 LTS instance
2. Configure security groups:
   - SSH (22) - Your IP
   - HTTP (80) - 0.0.0.0/0
   - HTTPS (443) - 0.0.0.0/0
   - Custom (8000) - 0.0.0.0/0 (Backend)
   - Custom (8501) - 0.0.0.0/0 (Frontend)

## Step 2: Connect and Setup
```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.9+
sudo apt install python3.9 python3.9-venv python3-pip nginx -y

# Install Node.js (for n8n if needed)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## Step 3: Deploy Application
```bash
# Clone repository
git clone https://github.com/your-username/your-repo.git
cd your-repo

# Create virtual environment
python3.9 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
nano .env  # Configure your variables
```

## Step 4: Configure Services
The deployment scripts will set up systemd services for automatic startup.
