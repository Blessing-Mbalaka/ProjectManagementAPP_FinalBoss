#!/bin/sh

set -e

echo "ðŸš€ Starting Django app on Azure..."

# Extract database host from DATABASE_URL if provided
if [ -n "$DATABASE_URL" ]; then
    # Extract hostname from DATABASE_URL (postgres://user:pass@HOST:port/db)
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=5432
    
    if [ -n "$DB_HOST" ]; then
        echo "â³ Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
        
        # Wait for database to be ready (with timeout)
        timeout=60
        while [ $timeout -gt 0 ]; do
            if nc -z "$DB_HOST" "$DB_PORT"; then
                echo "âœ… PostgreSQL is ready!"
                break
            fi
            echo "   Waiting for database... ($timeout seconds left)"
            sleep 2
            timeout=$((timeout - 2))
        done
        
        if [ $timeout -le 0 ]; then
            echo "âš ï¸  Database connection timeout, but continuing anyway..."
        fi
    fi
else
    echo "â„¹ï¸  No DATABASE_URL provided, skipping database check"
fi

echo "ðŸ”„ Running database migrations..."
python manage.py migrate --noinput

echo "ðŸ‘¤ Creating superuser if needed..."
python manage.py shell << 'PYEOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('âœ… Superuser created: admin/admin123')
else:
    print('â„¹ï¸  Superuser already exists')
PYEOF

echo "ðŸ“ Collecting static files..."
python manage.py collectstatic --noinput

echo "ðŸŒŸ Starting Django server..."
exec python manage.py runserver 0.0.0.0:8000