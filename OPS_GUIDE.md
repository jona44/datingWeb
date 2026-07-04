# Solo Admin Operations & Maintenance Guide

This document outlines the essential procedures, tools, and configurations required to keep the dating platform running smoothly on your VPS as a sole administrator.

---

## 1. Monitoring & Alerting (Knowing Before Users Do)

You cannot manually watch the server. You need to be alerted when things go wrong.

### External Uptime Monitoring
*   **Tools**: [UptimeRobot](https://uptimerobot.com/) or [Better Stack](https://betterstack.com/) (both offer generous free tiers).
*   **Configuration**: Setup an HTTP(S) monitor pointing to your landing or login page (e.g., `https://your-domain.com/accounts/login/`) checking every 5 minutes.
*   **Result**: If Nginx, Daphne, or the VPS goes offline, you will receive an immediate email/SMS/WhatsApp notification.

### Application Error Tracking
*   **Tool**: [Sentry](https://sentry.io/) (Free developer tier).
*   **Integration**: Add the Python SDK to your Django setup.
*   **Benefit**: Captures unhandled exceptions and database query failures in production, showing you the exact line of code that failed and under what conditions.

### Server Resource Alerts
*   **Tool**: [Netdata](https://www.netdata.cloud/) (Open-source, free).
*   **Setup**: Run their 1-line installation script on your VPS.
*   **Benefit**: Monitors CPU, RAM, and Disk space. Sends email alerts if disk space exceeds 80% or if RAM usage spikes into danger zones.

---

## 2. Server Security (Keeping Bots & Attackers Out)

A public VPS IP address is actively scanned by malicious bots within minutes of going live.

### SSH Hardening
Modify `/etc/ssh/sshd_config` to secure your access:
```ini
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```
> **IMPORTANT**: Make sure you have added your SSH public key to `/home/deploy/.ssh/authorized_keys` and verified you can log in *before* turning off password authentication!

Restart SSH to apply:
```bash
sudo systemctl restart ssh
```

### Brute-Force Prevention
Install and enable `fail2ban` to automatically ban IP addresses showing suspicious login behaviors:
```bash
sudo apt install -y fail2ban
```
The default configuration works out of the box to monitor SSH attempts and ban offenders for 24 hours.

### Automatic Security Patches
Keep the operating system packages secure without manual intervention:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```
This ensures critical security patches are downloaded and installed daily in the background.

---

## 3. Storage & Disk Management (Preventing Crashes)

If your 75GB SSD fills up to 100%, PostgreSQL will crash and potentially corrupt active tables.

### Media Offloading (Mandatory)
*   **Why**: Storing profile pictures, selfies, and user verification uploads on the VPS SSD is a storage risk and slows down the app.
*   **Solution**: Use an S3-compatible object storage provider like **Cloudflare R2** (10GB free tier, zero egress fees) or **Backblaze B2**.
*   **Implementation**: Install `django-storages` and configure `DEFAULT_FILE_STORAGE` to upload directly to R2.

### Log Rotation
Ubuntu handles log rotation automatically via `logrotate`. Verify that Nginx and system logs are compressed and discarded over time by checking `/etc/logrotate.d/`.

---

## 4. Database Maintenance (PostgreSQL)

### Connection Pooling
By default, Django opens a new connection to the database for every HTTP request.
*   **Tuning**: Set `'CONN_MAX_AGE': 600` inside your Django `DATABASES` settings dictionary. This allows Django to reuse database connections across requests, reducing the CPU load on PostgreSQL.

### Automated Backups Verification
The backup script created in `DEPLOYMENT_VPS.md` runs daily. However:
*   **Rule**: A backup is only valid if you have successfully restored it.
*   **Action**: Once a month, download the latest `.gz` dump from `/var/backups/dating/` and restore it to your local development database to verify data integrity.

---

## 5. Seamless Deployments (CI/CD)

Avoid manual FTP or file transfers. Create a deployment script on the server to make updates a single command.

Create a deployment script at `/home/deploy/deploy.sh`:
```bash
#!/bin/bash
set -e

PROJECT_DIR="/var/www/dating"
VENV_DIR="$PROJECT_DIR/env"

echo "=== Pulling latest changes ==="
cd $PROJECT_DIR
git pull origin main

echo "=== Activating Virtual Environment ==="
source $VENV_DIR/bin/activate

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Running Migrations ==="
python manage.py migrate

echo "=== Collecting Static Files ==="
python manage.py collectstatic --noinput

echo "=== Reloading Application Services ==="
sudo systemctl reload daphne
sudo systemctl restart celery
sudo systemctl restart celerybeat

echo "=== Deployment Successful! ==="
```

Make it executable:
```bash
chmod +x /home/deploy/deploy.sh
```

Run it whenever you want to deploy changes:
```bash
./deploy.sh
```

---

## 📋 The Solo Admin Weekly Routine (15 Minutes)

To ensure high availability and prevent minor issues from becoming major outages, perform these checks weekly:

1.  **Check Resources**: Log in via SSH and run `htop` to verify RAM usage and `df -h` to verify SSD space.
2.  **Verify Service Status**: Run `systemctl status daphne celery celerybeat postgresql redis-server nginx` to make sure all units are healthy.
3.  **Check Backups**: Run `ls -lh /var/backups/dating` to confirm the daily backup files are being generated and are not 0 bytes in size.
4.  **Security Updates**: Once a month, run `sudo apt update && sudo apt upgrade -y` followed by `sudo reboot` (schedule during low-traffic periods, e.g., 3:00 AM SADC time) to apply kernel-level security updates.
