#!/bin/bash
# ================================================================
# Script de Migración de SQLite a PostgreSQL
# Proyecto: Deliv - Plataforma de Delivery y Movilidad
# ================================================================
# Uso:
#   1. Asegúrate de tener PostgreSQL instalado y corriendo
#   2. Configura las variables en .env (USE_POSTGRESQL=True)
#   3. Ejecuta: bash scripts/migrate_to_postgresql.sh
# ================================================================

echo "=========================================="
echo " Inicio de migración SQLite -> PostgreSQL"
echo "=========================================="

# 1. Inicializar base de datos PostgreSQL
echo ""
echo "[1/5] Inicializando base de datos PostgreSQL..."
psql -U postgres -f scripts/init_db.sql
if [ $? -ne 0 ]; then
    echo "ERROR: No se pudo inicializar la base de datos."
    echo "Asegúrate de que PostgreSQL esté corriendo."
    exit 1
fi

# 2. Activar USE_POSTGRESQL en .env
echo ""
echo "[2/5] Activando USE_POSTGRESQL=True en .env..."
# Usar sed para reemplazar USE_POSTGRESQL=False por USE_POSTGRESQL=True
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' 's/USE_POSTGRESQL=False/USE_POSTGRESQL=True/' .env
else
    sed -i 's/USE_POSTGRESQL=False/USE_POSTGRESQL=True/' .env
fi

# 3. Exportar datos de SQLite
echo ""
echo "[3/5] Exportando datos desde SQLite..."
python manage.py dumpdata \
    --natural-foreign \
    --natural-primary \
    -e contenttypes \
    -e auth.Permission \
    --indent 2 \
    > backup.json

if [ $? -ne 0 ]; then
    echo "ERROR: No se pudo exportar los datos de SQLite."
    exit 1
fi
echo "Datos exportados a backup.json"

# 4. Aplicar migraciones en PostgreSQL
echo ""
echo "[4/5] Aplicando migraciones en PostgreSQL..."
python manage.py migrate --run-syncdb
if [ $? -ne 0 ]; then
    echo "ERROR: No se pudieron aplicar las migraciones."
    exit 1
fi

# 5. Importar datos a PostgreSQL
echo ""
echo "[5/5] Importando datos a PostgreSQL..."
python manage.py loaddata backup.json
if [ $? -ne 0 ]; then
    echo "ERROR: No se pudieron importar los datos."
    echo "Revisa posibles conflictos de datos."
    exit 1
fi

echo ""
echo "=========================================="
echo " Migración completada exitosamente!"
echo "=========================================="
echo "Tu base de datos ahora usa PostgreSQL."
echo ""
echo "Verifica con: python manage.py dbshell"
echo "             \\dt  (lista las tablas)"
echo "             SELECT count(*) FROM users_user;"
echo "=========================================="
