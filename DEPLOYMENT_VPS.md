# Linux VPS Deployment Guide

**Target OS:** Ubuntu 22.04 / 24.04 LTS
**Specs:** 4 CPU Cores, 8 GB RAM, 75 GB SSD
**Database:** PostgreSQL 16
**Cost:** ~R397/month

---

## 1. Initial Server Setup

SSH into your server:
```bash
ssh root@your-server-ip
```

Create a non-root sudo user (never run your app as root):
```bash
adduser deploy
usermod -aG sudo deploy
su - deploy
```

Update system:
```bash
sudo apt update && sudo apt upgrade -y
```

Install all dependencies:
```bash
sudo apt install -y \
  python3-venv python3-dev python3-pip \
  build-essential git \
  postgresql postgresql-contrib libpq-dev \
  redis-server \
  nginx \
  certbot python3-certbot-nginx \
  ufw
```

---

## 2. Firewall Setup

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 3. Swap Space (Safety Net for 8GB RAM)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
> This gives you a 2GB emergency buffer if RAM spikes during traffic peaks.

---

## 4. Database Setup — PostgreSQL

Start and enable PostgreSQL:
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

Create database and user:
```bash
sudo -u postgres psql
```
Inside the PostgreSQL prompt:
```sql
CREATE DATABASE dating_db;
CREATE USER dating_user WITH PASSWORD 'STRONG_PASSWORD_HERE';
ALTER ROLE dating_user SET client_encoding TO 'utf8';
ALTER ROLE dating_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE dating_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE dating_db TO dating_user;
\q
```

### Tune PostgreSQL for 8 GB RAM

Edit the PostgreSQL config:
```bash
sudo nano /etc/postgresql/16/main/postgresql.conf
```
Set these values:
```ini
# Memory
shared_buffers = 2GB               # 25% of RAM
effective_cache_size = 6GB         # 75% of RAM
work_mem = 64MB                    # Per sort/join operation
maintenance_work_mem = 512MB       # For VACUUM, CREATE INDEX

# Connections
max_connections = 100

# Write-ahead log
wal_buffers = 64MB
checkpoint_completion_target = 0.9

# Parallelism (4 cores)
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
```

Restart PostgreSQL to apply:
```bash
sudo systemctl restart postgresql
```

---

## 5. Redis Setup

```bash
sudo nano /etc/redis/redis.conf
```
Set these values:
```ini
maxmemory 512mb
maxmemory-policy allkeys-lru
save ""                            # Disable RDB snapshots (use append-only)
appendonly yes
```
```bash
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

---

## 6. Application Setup

Clone your repository:
```bash
cd /var/www
sudo git clone https://github.com/yourusername/dating.git
sudo chown -R deploy:deploy /var/www/dating
cd dating
```

Create Virtual Environment:
```bash
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary      # PostgreSQL driver
```

Create `.env` file:
```bash
cp .env.example .env
nano .env
```
> **Edit `.env`** — key values to set:
> ```
> DEBUG=False
> DATABASE_URL=postgresql://dating_user:STRONG_PASSWORD_HERE@localhost:5432/dating_db
> REDIS_URL=redis://localhost:6379/0
> ALLOWED_HOSTS=your-domain.com,www.your-domain.com
> SECRET_KEY=your-very-long-random-secret-key
> ```

Run Migrations and Collect Static:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

---

## 7. Configure Systemd — Daphne (ASGI Web Server)

Copy the service file:
```bash
sudo cp deployment/daphne.service /etc/systemd/system/
```

Make sure `deployment/daphne.service` is tuned for 4 CPUs:
```ini
[Unit]
Description=Daphne ASGI Server
After=network.target postgresql.service redis.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/dating
EnvironmentFile=/var/www/dating/.env
ExecStart=/var/www/dating/env/bin/daphne \
    -u /run/daphne/daphne.sock \
    --workers 4 \
    core.asgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create the socket directory:
```bash
sudo mkdir -p /run/daphne
sudo chown deploy:deploy /run/daphne
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl start daphne
sudo systemctl enable daphne
sudo systemctl status daphne
```

---

## 8. Configure Systemd — Celery Workers

```bash
sudo nano /etc/systemd/system/celery.service
```
```ini
[Unit]
Description=Celery Workers
After=network.target redis.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/dating
EnvironmentFile=/var/www/dating/.env
ExecStart=/var/www/dating/env/bin/celery \
    -A core worker \
    --loglevel=info \
    --concurrency=2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/systemd/system/celerybeat.service
```
```ini
[Unit]
Description=Celery Beat Scheduler
After=network.target redis.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/dating
EnvironmentFile=/var/www/dating/.env
ExecStart=/var/www/dating/env/bin/celery \
    -A core beat \
    --loglevel=info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery celerybeat
sudo systemctl start celery celerybeat
```

---

## 9. Configure Nginx (Reverse Proxy)

```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/dating
sudo ln -s /etc/nginx/sites-available/dating /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Ensure `deployment/nginx.conf` serves media, static, and proxies WebSockets:
```nginx
upstream daphne {
    server unix:/run/daphne/daphne.sock fail_timeout=0;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/dating/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/dating/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

---

## 10. HTTPS (SSL with Certbot)

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Certbot auto-renews via systemd timer. Verify:
```bash
sudo certbot renew --dry-run
```

---

## 11. Automated Daily Database Backups

```bash
sudo mkdir -p /var/backups/dating
sudo nano /usr/local/bin/backup_dating_db.sh
```
```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/dating
pg_dump -U dating_user -h localhost dating_db | gzip > "$BACKUP_DIR/dating_db_$TIMESTAMP.gz"
# Keep only last 7 days
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete
```
```bash
sudo chmod +x /usr/local/bin/backup_dating_db.sh
```

Add to cron (runs every day at 3am):
```bash
sudo crontab -e
```
```
0 3 * * * /usr/local/bin/backup_dating_db.sh
```

---

## 12. Troubleshooting

| Issue | Command |
|---|---|
| App logs | `journalctl -u daphne -f` |
| Celery logs | `journalctl -u celery -f` |
| Nginx errors | `tail -f /var/log/nginx/error.log` |
| PostgreSQL logs | `tail -f /var/log/postgresql/postgresql-16-main.log` |
| Redis status | `redis-cli ping` |
| Disk usage | `df -h` |
| RAM usage | `free -h` |
| CPU load | `htop` |
| All services status | `systemctl status daphne celery celerybeat nginx postgresql redis-server` |
