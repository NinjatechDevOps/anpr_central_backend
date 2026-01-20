#!/bin/bash
# Script to create a new Alembic migration
# Usage:
#   Local: ./scripts/create_migration.sh 'migration message'
#   Docker: docker exec vehicle-detection-api ./scripts/create_migration.sh 'migration message'

set -e

if [ -z "$1" ]; then
    echo "Usage: ./scripts/create_migration.sh 'migration message'"
    echo ""
    echo "Examples:"
    echo "  Local:  ./scripts/create_migration.sh 'add_user_table'"
    echo "  Docker: docker exec vehicle-detection-api ./scripts/create_migration.sh 'add_user_table'"
    exit 1
fi

echo "🔄 Creating migration: $1"
alembic revision --autogenerate -m "$1"

if [ $? -eq 0 ]; then
    echo "✅ Migration created successfully"
    echo ""
    echo "Next steps:"
    echo "1. Review the generated migration file in alembic/versions/"
    echo "2. Run migration: ./scripts/migrate.sh (or docker exec vehicle-detection-api ./scripts/migrate.sh)"
else
    echo "❌ Migration creation failed"
    exit 1
fi
