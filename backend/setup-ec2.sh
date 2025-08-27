#!/bin/bash

# EC2 Setup Script for DTCC-Table
# Run this once on a fresh Ubuntu EC2 instance

echo "Setting up DTCC-Table on EC2..."

# Update system
sudo apt update
sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install Git
sudo apt install -y git

# Install nginx for reverse proxy (optional but recommended)
sudo apt install -y nginx

# Create app directory
mkdir -p /home/ubuntu/dtcc-table

# Configure nginx (optional)
sudo tee /etc/nginx/sites-available/dtcc-table > /dev/null <<EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/dtcc-table /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Configure firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8001
sudo ufw --force enable

echo "EC2 setup complete!"
echo ""
echo "Next steps:"
echo "1. Add GitHub secrets in your repository:"
echo "   - EC2_SSH_PRIVATE_KEY: Your EC2 instance private key"
echo "   - EC2_HOST: Your EC2 public IP or domain"
echo "   - EC2_USER: ubuntu (default)"
echo "   - SECRET_KEY: Generate with: openssl rand -hex 32"
echo ""
echo "2. Push to GitHub main branch to deploy"
echo ""
echo "3. Access your app at http://YOUR_EC2_IP"