# Deploy latest origin/main to VPS
Write-Host "🌐 Deploying latest origin/main to VPS (102.208.228.164)..." -ForegroundColor Cyan

ssh -o BatchMode=yes deploy@102.208.228.164 @"
set -e
cd /var/www/dating
git fetch origin
git reset --hard origin/main
source /var/www/dating/env/bin/activate
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart daphne
if systemctl is-active --quiet celery; then
    sudo systemctl restart celery
fi
if systemctl is-active --quiet celerybeat; then
    sudo systemctl restart celerybeat
fi
echo '✅ VPS deployment completed successfully!'
"@
