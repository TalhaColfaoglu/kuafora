#!/bin/bash

# Active User Tracking Setup Script
# Bu script yeni tracking sistemini kurar

set -e  # Hata durumunda dur

echo "========================================="
echo "Active User Tracking Setup"
echo "========================================="
echo ""

# Renk kodları
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Container adı
CONTAINER_NAME="kuafora-backend"

echo -e "${YELLOW}Step 1: Checking if container is running...${NC}"
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${RED}Error: Container $CONTAINER_NAME is not running!${NC}"
    echo "Please start the container first: docker-compose up -d"
    exit 1
fi
echo -e "${GREEN}✓ Container is running${NC}"
echo ""

echo -e "${YELLOW}Step 2: Creating migrations...${NC}"
docker exec $CONTAINER_NAME python manage.py makemigrations analytics
echo -e "${GREEN}✓ Migrations created${NC}"
echo ""

echo -e "${YELLOW}Step 3: Running migrations...${NC}"
docker exec $CONTAINER_NAME python manage.py migrate analytics
echo -e "${GREEN}✓ Migrations applied${NC}"
echo ""

echo -e "${YELLOW}Step 4: Testing models...${NC}"
docker exec $CONTAINER_NAME python manage.py shell -c "
from app.analytics.models import UserActivityLog, DailyMetrics
print('UserActivityLog table: OK')
print('DailyMetrics table: OK')
print('Current UserActivityLog count:', UserActivityLog.objects.count())
print('Current DailyMetrics count:', DailyMetrics.objects.count())
"
echo -e "${GREEN}✓ Models are working${NC}"
echo ""

echo -e "${YELLOW}Step 5: Creating test tracking data...${NC}"
docker exec $CONTAINER_NAME python manage.py shell -c "
from app.analytics.utils import track_login
from app.users.models import User
from datetime import date

# İlk staff olmayan kullanıcıyı bul
user = User.objects.filter(is_staff=False, is_superuser=False).first()
if user:
    track_login(
        user=user,
        device_id='test_device_setup_123',
        app_type='main',
        platform='iOS',
        app_version='1.0.0',
        os_version='17.0'
    )
    print(f'✓ Test tracking created for user: {user.email}')
    
    from app.analytics.models import UserActivityLog
    today_count = UserActivityLog.objects.filter(activity_date=date.today()).count()
    print(f'✓ Today activity logs: {today_count}')
else:
    print('⚠ No non-staff users found. Create a test user first.')
"
echo -e "${GREEN}✓ Test data created${NC}"
echo ""

echo -e "${YELLOW}Step 6: Calculating daily metrics for last 7 days...${NC}"
docker exec $CONTAINER_NAME python manage.py calculate_daily_metrics --backfill 7
echo -e "${GREEN}✓ Daily metrics calculated${NC}"
echo ""

echo -e "${YELLOW}Step 7: Verifying dashboard data...${NC}"
docker exec $CONTAINER_NAME python manage.py shell -c "
from app.analytics.models import UserActivityLog, DailyMetrics
from datetime import date

# Bugünkü aktivite
today_activities = UserActivityLog.objects.filter(
    activity_date=date.today(),
    app_type='main'
).values('device_id').distinct().count()

# DailyMetrics kayıtları
daily_metrics_count = DailyMetrics.objects.count()

print('=' * 50)
print('DASHBOARD DATA VERIFICATION')
print('=' * 50)
print(f'Today Active Devices: {today_activities}')
print(f'DailyMetrics Records: {daily_metrics_count}')
print('=' * 50)

if today_activities > 0:
    print('✓ Dashboard should show active users now!')
else:
    print('⚠ No active users today. Activity tracking working, waiting for real user logins.')
"
echo -e "${GREEN}✓ Dashboard data verified${NC}"
echo ""

echo "========================================="
echo -e "${GREEN}Setup Completed Successfully!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. ✓ Database models created"
echo "2. ✓ Test data added"
echo "3. ✓ Daily metrics calculated"
echo ""
echo "What to do next:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Go to admin dashboard: https://your-domain.com/admin/"
echo "2. Check 'Kuafora Dashboard' - you should see metrics now"
echo "3. Add tracking to your login endpoints (see ACTIVE_USER_TRACKING_SETUP.md)"
echo "4. Setup cron job for daily metrics:"
echo "   crontab -e"
echo "   Add: 0 1 * * * docker exec $CONTAINER_NAME python manage.py calculate_daily_metrics"
echo ""
echo "📖 Full documentation: ACTIVE_USER_TRACKING_SETUP.md"
echo ""
