#!/bin/bash

# Configuración del proyecto
echo "🚀 Configurando proyecto DeliversST..."

# Crear directorios necesarios
mkdir -p logs
mkdir -p media/profile_pics
mkdir -p media/products
mkdir -p media/categories
mkdir -p static

# Instalar dependencias
echo "📦 Instalando dependencias..."
pip install -r requirements.txt

# Aplicar migraciones
echo "🗃️ Aplicando migraciones..."
python manage.py makemigrations
python manage.py migrate

# Crear tipos de notificaciones
echo "🔔 Creando tipos de notificaciones..."
python manage.py create_notification_types

# Crear superusuario
echo "👤 Creando superusuario..."
python manage.py setup_admin

# Crear datos de ejemplo
echo "📊 Creando datos de ejemplo..."
python manage.py create_sample_data
python manage.py create_sample_delivery
python manage.py create_sample_drivers

# Collectstatic (para producción)
echo "📁 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "✅ ¡Proyecto configurado correctamente!"
echo "🌐 Ejecuta: python manage.py runserver"
echo "📱 API disponible en: http://localhost:8000/api/"
echo "🔧 Admin en: http://localhost:8000/admin/"
echo "👤 Usuario admin: admin / admin123"