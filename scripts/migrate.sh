#!/bin/bash
# Script to run database migrations
# Usage:
#   Local: ./scripts/migrate.sh
#   Docker: docker exec vehicle-detection-api ./scripts/migrate.sh

set -e

echo "🔄 Running database migrations..."
echo ""

# Show current migration status
echo "Current migration status:"
alembic current

echo ""
echo "Upgrading to latest migration..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migrations completed successfully"
    echo ""
    echo "New migration status:"
    alembic current
else
    echo ""
    echo "❌ Migration failed"
    exit 1
fi
