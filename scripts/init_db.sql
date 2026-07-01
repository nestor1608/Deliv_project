-- ================================================================
-- Script de Inicialización de Base de Datos PostgreSQL
-- Proyecto: Deliv - Plataforma de Delivery y Movilidad
-- ================================================================
-- Uso:
--   psql -U postgres -f scripts/init_db.sql
-- ================================================================

-- Eliminar base de datos si existe (solo para reset de desarrollo)
DROP DATABASE IF EXISTS deliv_db;

-- Crear base de datos
CREATE DATABASE deliv_db
    ENCODING 'UTF8'
    LC_COLLATE 'en_US.UTF-8'
    LC_CTYPE 'en_US.UTF-8';

-- Crear usuario dedicado
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'deliv_user') THEN
        CREATE ROLE deliv_user WITH LOGIN PASSWORD 'deliv_pass_segura';
    END IF;
END
$$;

-- Otorgar privilegios
GRANT ALL PRIVILEGES ON DATABASE deliv_db TO deliv_user;

-- Conectar a la base de datos recién creada
\c deliv_db;

-- Otorgar permisos sobre el schema public
GRANT ALL ON SCHEMA public TO deliv_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO deliv_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO deliv_user;

-- Configurar permisos por defecto para nuevas tablas
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO deliv_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO deliv_user;

-- Extensión para UUID (si se usa en el proyecto)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extensión para búsqueda de texto completo (operaciones de búsqueda)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Verificación final
SELECT 'Base de datos deliv_db creada exitosamente' AS resultado;
SELECT version();
\endecho;
