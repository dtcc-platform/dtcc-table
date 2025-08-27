# AWS EC2 Deployment Guide for DTCC-Table

## 🚀 Prerequisites

1. **AWS Account** with EC2 access
2. **GitHub Repository** with your code
3. **EC2 Instance** (Ubuntu 22.04 recommended)

## 📋 Step-by-Step Deployment

### Step 1: Launch EC2 Instance

1. **Go to AWS Console** → EC2 → Launch Instance

2. **Configure Instance:**
   - Name: `dtcc-table-server`
   - OS: Ubuntu Server 22.04 LTS
   - Instance Type: t2.micro (free tier)
   - Key Pair: Create new or use existing
   - Security Group Rules:
     - SSH (22) - Your IP
     - HTTP (80) - Anywhere
     - Custom TCP (8001) - Anywhere

3. **Launch and wait for instance to start**

### Step 2: Initial EC2 Setup

1. **SSH into your instance:**
   ```bash
   ssh -i your-key.pem ubuntu@YOUR_EC2_IP
   ```

2. **Run the setup script:**
   ```bash
   # Download setup script
   wget https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/dtcc-table/main/backend/setup-ec2.sh
   
   # Make executable and run
   chmod +x setup-ec2.sh
   ./setup-ec2.sh
   ```

   This script will:
   - Install Python 3.11
   - Install and configure nginx
   - Setup firewall rules
   - Create application directory

### Step 3: Configure GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `EC2_SSH_PRIVATE_KEY` | Content of your .pem file | The private key to SSH into EC2 |
| `EC2_HOST` | Your EC2 public IP | e.g., 54.123.45.67 |
| `EC2_USER` | ubuntu | Default EC2 username |
| `SECRET_KEY` | Random string | Generate: `openssl rand -hex 32` |

#### How to add EC2_SSH_PRIVATE_KEY:
```bash
# Copy your private key content
cat your-key.pem
# Paste entire content including BEGIN and END lines
```

### Step 4: Deploy via GitHub Actions

1. **Push your code to GitHub:**
   ```bash
   git add .
   git commit -m "Deploy to EC2"
   git push origin main
   ```

2. **GitHub Actions will automatically:**
   - Connect to your EC2 instance
   - Pull latest code
   - Install dependencies
   - Start the application

3. **Monitor deployment:**
   - Go to GitHub → Actions tab
   - Watch the deployment progress

### Step 5: Access Your Application

After successful deployment:

1. **Access via EC2 IP:**
   ```
   http://YOUR_EC2_IP
   ```

2. **Default credentials:**
   - Username: `vasnas`
   - Password: `admin123`
   - **⚠️ Change immediately after first login!**

## 🔧 Manual Deployment (Alternative)

If you prefer to deploy manually:

1. **SSH into EC2:**
   ```bash
   ssh -i your-key.pem ubuntu@YOUR_EC2_IP
   ```

2. **Clone repository:**
   ```bash
   cd /home/ubuntu
   git clone https://github.com/YOUR_GITHUB_USERNAME/dtcc-table.git
   cd dtcc-table/backend
   ```

3. **Setup Python environment:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Create environment file:**
   ```bash
   echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
   echo "DATABASE_URL=sqlite:///./users.db" >> .env
   ```

5. **Run application:**
   ```bash
   python app.py
   ```

   Or use systemd service:
   ```bash
   sudo cp dtcc-table.service /etc/systemd/system/
   sudo systemctl start dtcc-table
   sudo systemctl enable dtcc-table
   ```

## 🔒 Security Configuration

### Enable HTTPS with Let's Encrypt

1. **Point domain to EC2 IP** (if you have a domain)

2. **Install Certbot:**
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   ```

3. **Get SSL certificate:**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

### Configure Firewall

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### Secure the Database

```bash
# Backup database regularly
crontab -e
# Add: 0 2 * * * cp /home/ubuntu/dtcc-table/backend/users.db /home/ubuntu/backups/users-$(date +\%Y\%m\%d).db
```

## 📊 Monitoring

### Check Application Status

```bash
# Via systemd
sudo systemctl status dtcc-table

# View logs
sudo journalctl -u dtcc-table -f

# Check if running
curl http://localhost:8001
```

### Monitor Server Resources

```bash
# CPU and Memory
htop

# Disk usage
df -h

# Network connections
sudo netstat -tlnp
```

## 🔄 Updating the Application

### Automatic (via GitHub push)

Simply push to main branch:
```bash
git push origin main
```

GitHub Actions will handle the deployment.

### Manual Update

```bash
cd /home/ubuntu/dtcc-table
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart dtcc-table
```

## 🆘 Troubleshooting

### Application Not Starting

```bash
# Check logs
sudo journalctl -u dtcc-table -n 50

# Check if port is in use
sudo lsof -i :8001

# Restart service
sudo systemctl restart dtcc-table
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R ubuntu:ubuntu /home/ubuntu/dtcc-table

# Fix upload directory permissions
chmod 755 /home/ubuntu/dtcc-table/backend/static/assets
```

### Database Issues

```bash
# Check database integrity
sqlite3 users.db "PRAGMA integrity_check;"

# Reset database (WARNING: Deletes all data)
rm users.db
python app.py  # Will create fresh database
```

## 🌐 Custom Domain Setup

1. **In AWS Route 53** (or your DNS provider):
   - Create A record pointing to EC2 IP

2. **Update nginx configuration:**
   ```bash
   sudo nano /etc/nginx/sites-available/dtcc-table
   # Change server_name from _ to your-domain.com
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## 💰 Cost Optimization

- **Use t2.micro** for free tier (750 hours/month for first year)
- **Stop instance** when not in use
- **Use Elastic IP** to maintain same IP address
- **Set up CloudWatch alarms** for billing alerts

## 📝 Maintenance Checklist

- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`
- [ ] Monitor disk space: `df -h`
- [ ] Check logs weekly: `sudo journalctl -u dtcc-table`
- [ ] Backup database: Setup automated backups
- [ ] Review access logs: `/var/log/nginx/access.log`
- [ ] Update dependencies: `pip list --outdated`

## 🚨 Important Notes

1. **Change default password** immediately after deployment
2. **Keep SECRET_KEY secure** - never commit to repository
3. **Regular backups** - automate database backups
4. **Monitor costs** - set up AWS billing alerts
5. **Security updates** - regularly update system packages

## 📞 Support

For deployment issues:
1. Check GitHub Actions logs
2. Review EC2 instance logs
3. Open issue in repository