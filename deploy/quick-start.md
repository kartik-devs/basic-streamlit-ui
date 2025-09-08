# Quick EC2 Deployment

## 1. Launch EC2 Instance
- **Instance Type**: t3.medium or larger (2GB+ RAM recommended)
- **OS**: Ubuntu 20.04 LTS
- **Storage**: 20GB+ EBS volume
- **Security Groups**: 
  - SSH (22) - Your IP
  - HTTP (80) - 0.0.0.0/0
  - HTTPS (443) - 0.0.0.0/0

## 2. Connect to EC2
```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

## 3. Run Deployment Script
```bash
# Upload your project files to EC2 first
scp -r -i your-key.pem . ubuntu@your-ec2-public-ip:~/OCR/

# Then run the deployment script
cd ~/OCR
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## 4. Configure Environment
```bash
# Edit environment variables
nano .env

# Update with your actual values:
# - AWS credentials
# - S3 bucket name
# - GitHub token
# - Backend URL
```

## 5. Restart Services
```bash
sudo systemctl restart backend frontend nginx
```

## 6. Access Your App
- **Frontend**: http://your-ec2-public-ip
- **Backend API**: http://your-ec2-public-ip/api/
- **Health Check**: http://your-ec2-public-ip/health

## 7. Set Up SSL (Optional)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Monitoring
```bash
# Check service status
sudo systemctl status backend frontend nginx

# View logs
sudo journalctl -u backend -f
sudo journalctl -u frontend -f

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```
