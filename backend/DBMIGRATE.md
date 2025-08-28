# Database Migration Guide

This guide explains how to update your database schema when deploying new features that require database changes.

## Current Migration: Add `processed_size` Column

The latest update adds support for GeoPackage files with automatic rasterization. This requires a new database column called `processed_size` to track whether GeoPackage files were clipped or expanded during processing.

## Migration Options

### Option 1: Migrate Existing Database (Recommended - Preserves All Data)

Use this option if you have existing users, projects, and files you want to keep.

1. SSH into your EC2 instance:
```bash
ssh -i your-key.pem ubuntu@your-ec2-instance
```

2. Navigate to the backend directory:
```bash
cd /home/ubuntu/dtcc-table/backend
```

3. Pull the latest code (if using git):
```bash
git pull origin main
```

4. Run the migration script:
```bash
python3.11 migrate_db.py
```

This script will:
- Create a timestamped backup of your database
- Add the new `processed_size` column to the `uploaded_files` table
- Preserve all existing data (users, projects, files)

5. Restart the service:
```bash
sudo systemctl restart dtcc-table
```

6. Verify the service is running:
```bash
sudo systemctl status dtcc-table
```

### Option 2: Fresh Database (Quick Setup - Loses All Data)

Use this option only if you don't have important data or are setting up a new instance.

1. SSH into your EC2 instance:
```bash
ssh -i your-key.pem ubuntu@your-ec2-instance
```

2. Navigate to the backend directory:
```bash
cd /home/ubuntu/dtcc-table/backend
```

3. Pull the latest code (if using git):
```bash
git pull origin main
```

4. Backup and remove the old database:
```bash
mv users.db users_backup_$(date +%Y%m%d_%H%M%S).db
```

5. Restart the service (this will create a new database):
```bash
sudo systemctl restart dtcc-table
```

6. Recreate your admin user:
```bash
python3.11 add_admin.py vasnas yourpassword
```

7. Verify the service is running:
```bash
sudo systemctl status dtcc-table
```

## Troubleshooting

### If the migration fails:

1. Check the error message from the migration script
2. Restore from the automatic backup:
```bash
# Find the backup file (created by migration script)
ls -la users_backup_*.db

# Restore the backup
cp users_backup_TIMESTAMP.db users.db

# Restart the service
sudo systemctl restart dtcc-table
```

### If the service won't start:

1. Check the service logs:
```bash
sudo journalctl -u dtcc-table -n 50
```

2. Check Python dependencies are installed:
```bash
cd /home/ubuntu/dtcc-table/backend
source venv/bin/activate
pip install -r requirements.txt
```

3. Verify database permissions:
```bash
ls -la users.db
# Should be owned by ubuntu:ubuntu
sudo chown ubuntu:ubuntu users.db
```

## Future Migrations

When new database changes are introduced:

1. A new migration script will be provided or the existing `migrate_db.py` will be updated
2. Always backup your database before migrating
3. Test migrations in a development environment first if possible
4. Keep track of which migrations have been applied

## Database Backup Best Practices

1. **Regular Backups**: Set up a cron job for regular backups:
```bash
# Add to crontab (crontab -e)
0 2 *ためて * cd /home/ubuntu/dtcc-table/backend && cp users.db backups/users_$(date +\%Y\%m\%d).db
```

2. **Before Updates**: Always backup before updating the application:
```bash
cp users.db users_backup_$(date +%Y%m%d_%H%M%S).db
```

3. **Off-site Backups**: Consider copying backups to S3 or another location:
```bash
aws s3 cp users.db s3://your-backup-bucket/dtcc-table/users_$(date +%Y%m%d).db
```