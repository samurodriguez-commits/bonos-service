"""
db.py — Conexión a PostgreSQL (compartida con el casino-backend).

Patrón 12-factor: toda la configuración viene de variables de entorno.
Este servicio comparte la MISMA base de datos que casino-backend, por eso
puede leer/escribir las tablas `usuarios` y `transacciones`. Sus tablas
propias (`bonos`, `bonos_reclamados`) las crea al arrancar de forma idempotente.
"""
import os
import time

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2 import extensions

# Postgres devuelve NUMERIC como string/Decimal. Igual que casino-backend
# (types.setTypeParser(1700, parseFloat)), lo convertimos a float para que la
# API responda números JSON nativos en saldos y montos.
_DEC2FLOAT = extensions.new_type(
    extensions.DECIMAL.values,
    "DEC2FLOAT",
    lambda value, curs: float(value) if value is not None else None,
)
extensions.register_type(_DEC2FLOAT)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "casino"),
    "password": os.getenv("DB_PASSWORD", "casino"),
    "dbname": os.getenv("DB_NAME", "casino_db"),
}

# Pool de conexiones apto para los hilos del threadpool de FastAPI.
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def esperar_bd(max_intentos: int = 30, espera_s: float = 2.0) -> None:
    """Reintenta hasta que Postgres acepte consultas (arranque asincrónico)."""
    global _pool
    ultimo_error = None
    for intento in range(1, max_intentos + 1):
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, **DB_CONFIG)
            conn = _pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            _pool.putconn(conn)
            print(f"[PG] Conexión establecida (intento {intento})", flush=True)
            return
        except Exception as err:  # noqa: BLE001 — log y reintento didáctico
            ultimo_error = err
            print(f"[PG] BD no disponible ({intento}/{max_intentos}): {err}", flush=True)
            time.sleep(espera_s)
    raise RuntimeError(f"No se pudo conectar a Postgres: {ultimo_error}")


class _Conexion:
    """Context manager: presta una conexión del pool y la devuelve siempre."""

    def __enter__(self):
        self.conn = _pool.getconn()
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.conn.rollback()
        _pool.putconn(self.conn)


def conexion() -> _Conexion:
    return _Conexion()


def dict_cursor(conn):
    """Cursor que devuelve filas como diccionarios."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ------------------------------------------------------------------
# Esquema propio del servicio (idempotente). Las tablas base usuarios /
# transacciones las crea casino-backend/db/init.sql en el initdb de Postgres.
# ------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS bonos (
  id           SERIAL PRIMARY KEY,
  codigo       VARCHAR(40)  NOT NULL UNIQUE,
  nombre       VARCHAR(80)  NOT NULL,
  descripcion  TEXT,
  tipo         VARCHAR(20)  NOT NULL CHECK (tipo IN ('monto_fijo','porcentaje')),
  valor        NUMERIC(12,2) NOT NULL,
  un_solo_uso  BOOLEAN      NOT NULL DEFAULT TRUE,
  activo       BOOLEAN      NOT NULL DEFAULT TRUE,
  creado_en    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bonos_reclamados (
  id              SERIAL PRIMARY KEY,
  usuario_id      INTEGER      NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  bono_id         INTEGER      NOT NULL REFERENCES bonos(id),
  monto_otorgado  NUMERIC(12,2) NOT NULL,
  reclamado_en    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bonos_recl_usuario ON bonos_reclamados(usuario_id);
"""

_SEED = """
INSERT INTO bonos (codigo, nombre, descripcion, tipo, valor, un_solo_uso) VALUES
  ('bienvenida', 'Bono de Bienvenida', 'Crédito fijo de regalo al unirte. Una sola vez.', 'monto_fijo', 5000, TRUE),
  ('recarga',    'Bono de Recarga',    'Suma un % sobre el monto que recargues.',         'porcentaje', 50,   FALSE),
  ('cashback',   'Cashback Semanal',   'Devuelve un % de lo apostado (sobre monto_base).','porcentaje', 10,   FALSE)
ON CONFLICT (codigo) DO NOTHING;
"""


def init_schema() -> None:
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
            cur.execute(_SEED)
        conn.commit()
    print("[PG] Esquema de bonos verificado/sembrado", flush=True)


def ping() -> bool:
    """Chequeo de salud de la BD para /health."""
    try:
        with conexion() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False
