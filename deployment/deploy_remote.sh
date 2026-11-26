#!/usr/bin/env bash
set -e

echo "=== 1. Tuning PostgreSQL ==="
sudo -u postgres psql -c "ALTER USER dating_user WITH PASSWORD 'DatingSecure_2026_x9Qv7!';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE dating_db TO dating_user;"
sudo -u postgres psql -d dating_db -c "GRANT ALL ON SCHEMA public TO dating_user; ALTER SCHEMA public OWNER TO dating_user;"

PG_CONF_DIR=$(dirname $(ls /etc/postgresql/*/main/postgresql.conf | head -n 1))/conf.d
sudo mkdir -p "$PG_CONF_DIR"
cat << 'EOF' | sudo tee "$PG_CONF_DIR/99-tuning.conf"
# Custom Performance Tuning
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 64MB
maintenance_work_mem = 512MB
max_connections = 200
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
EOF

sudo systemctl restart postgresql
echo "PostgreSQL configured and restarted."

echo "=== 2. Tuning Redis ==="
sudo sed -i '/^maxmemory /d' /etc/redis/redis.conf
sudo sed -i '/^maxmemory-policy /d' /etc/redis/redis.conf
sudo sed -i '/^appendonly /d' /etc/redis/redis.conf
echo "maxmemory 512mb" | sudo tee -a /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" | sudo tee -a /etc/redis/redis.conf
echo "appendonly yes" | sudo tee -a /etc/redis/redis.conf
sudo systemctl restart redis-server
echo "Redis configured and restarted."

echo "=== 3. Setting up Repository in /var/www/dating ==="
sudo mkdir -p /var/www
sudo chown -R deploy:deploy /var/www

if [ ! -d "/var/www/dating/.git" ]; then
    echo "Cloning repository..."
    git clone https://github.com/jona44/datingWeb.git /var/www/dating
else
    echo "Updating existing repository..."
    cd /var/www/dating
    git fetch origin
    git reset --hard origin/main
fi

cd /var/www/dating
sudo chown -R deploy:deploy /var/www/dating

echo "=== 4. Setting up Python Virtual Environment ==="
if [ ! -d "/var/www/dating/env" ]; then
    python3 -m venv /var/www/dating/env
fi

source /var/www/dating/env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary

echo "=== 5. Writing Production .env ==="
cat << 'EOF' > /var/www/dating/.env
# Django Production Settings
DEBUG=False
SECRET_KEY=prod-sec-9f82k4b92h58v104n285g93b8274g2958h2
ALLOWED_HOSTS=102.208.228.164,localhost,127.0.0.1,lovebyte.online,www.lovebyte.online,loveplus.online,www.loveplus.online,getloveplus.online,www.getloveplus.online,hivplus.local,diversehearts.local,*
CSRF_TRUSTED_ORIGINS=http://102.208.228.164,https://102.208.228.164,http://lovebyte.online,https://lovebyte.online,http://www.lovebyte.online,https://www.lovebyte.online,http://loveplus.online,https://loveplus.online,http://www.loveplus.online,https://www.loveplus.online,http://getloveplus.online,https://getloveplus.online,http://www.getloveplus.online,https://www.getloveplus.online

# Database & Cache
DATABASE_URL=postgresql://dating_user:DatingSecure_2026_x9Qv7!@localhost:5432/dating_db
DB_CONN_MAX_AGE=0
REDIS_URL=redis://127.0.0.1:6379/1

# Authentication & Application Variants
ACCOUNT_DEFAULT_HTTP_PROTOCOL=http
APP_VARIANT=hiv_plus
HIV_PLUS_DOMAIN=getloveplus.online,www.getloveplus.online,loveplus.online,www.loveplus.online,hivplus.local
GENERAL_DOMAIN=lovebyte.online,www.lovebyte.online,diversehearts.local

# Social Auth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
FACEBOOK_CLIENT_ID=your-facebook-client-id
FACEBOOK_CLIENT_SECRET=your-facebook-client-secret

# SMS
SMS_BACKEND=accounts.sms.BulkSMSBackend
# BULKSMS_TOKEN_ID=your-bulksms-token-id
# BULKSMS_TOKEN_SECRET=your-bulksms-token-secret
PHONENUMBER_DEFAULT_REGION=ZA
OTP_EXPIRATION_SECONDS=300
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5
DEV_FIXED_OTP=123456
EOF

chmod 600 /var/www/dating/.env

echo "=== 6. Building Tailwind CSS Assets ==="
cd /var/www/dating
if [ -d "theme/static_src" ]; then
    npm --prefix theme/static_src install
    npm --prefix theme/static_src run build
fi

echo "=== 7. Running Migrations & Collecting Static Files ==="
cd /var/www/dating
source /var/www/dating/env/bin/activate
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "=== 8. Configuring Daphne ASGI Service ==="
sudo mkdir -p /run/daphne
sudo chown deploy:deploy /run/daphne
echo "d /run/daphne 0755 deploy deploy -" | sudo tee /etc/tmpfiles.d/daphne.conf

cat << 'EOF' | sudo tee /etc/systemd/system/daphne.service
[Unit]
Description=Daphne ASGI Server
After=network.target postgresql.service redis-server.service

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
EOF

sudo systemctl daemon-reload
sudo systemctl enable daphne
sudo systemctl restart daphne

echo "=== 9. Configuring Nginx ==="
cat << 'EOF' | sudo tee /etc/nginx/sites-available/dating
upstream daphne {
    server unix:/run/daphne/daphne.sock fail_timeout=0;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name 102.208.228.164 lovebyte.online www.lovebyte.online loveplus.online www.loveplus.online _;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/dating/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/dating/media/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
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
EOF

sudo ln -sf /etc/nginx/sites-available/dating /etc/nginx/sites-enabled/dating
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "=== Deployment Completed Successfully! ==="
