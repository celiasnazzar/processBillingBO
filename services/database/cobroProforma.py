import pymysql
from typing import Optional
from settings import settings

VISTA_EMAIL = "v_consulta_email"

class DatabaseUnavailable(Exception):
    """Sin configuración de BD o fallo de conexión/consulta."""

def _ssl_config() -> Optional[dict]:
    """Igual que cobro-gateway: certificados si hay alguna ruta, si no DB_SSL=required, si no sin SSL."""
    if settings.DB_SSL_CA or settings.DB_SSL_CERT or settings.DB_SSL_KEY:
        ssl = {}
        if settings.DB_SSL_CA:   ssl["ca"] = settings.DB_SSL_CA
        if settings.DB_SSL_CERT: ssl["cert"] = settings.DB_SSL_CERT
        if settings.DB_SSL_KEY:  ssl["key"] = settings.DB_SSL_KEY
        return ssl
    if settings.DB_SSL.lower() == "required":
        # Sin CA: cifra pero no valida el certificado del servidor.
        return {"check_hostname": False}
    return None

def find_client_email(num_pedido: int) -> Optional[str]:
    """Busca el email del cliente en v_consulta_email por nº de pedido.
    Devuelve None si el pedido no existe o no tiene email.
    Lanza DatabaseUnavailable si no hay configuración o falla la conexión."""
    if not settings.DB_PASSWORD:
        print("BD: falta DB_PASSWORD, no se consulta el email")
        raise DatabaseUnavailable("Falta DB_PASSWORD")

    sql = (
        f"SELECT correo FROM `{VISTA_EMAIL}` "
        "WHERE CPM_NUMERO_PEDIDO = %s "
        "AND correo IS NOT NULL AND TRIM(correo) <> '' LIMIT 1"
    )
    try:
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset="utf8mb4",
            connect_timeout=settings.DB_CONNECT_TIMEOUT_S,
            ssl=_ssl_config(),
        )
        try:
            with conn.cursor() as cur:
                # CPM_NUMERO_PEDIDO es double en la vista: se compara como número
                cur.execute(sql, (int(num_pedido),))
                row = cur.fetchone()
        finally:
            conn.close()
    except (pymysql.MySQLError, OSError) as e:
        print("BD: error consultando email:", e)
        raise DatabaseUnavailable(str(e)) from e

    return row[0] if row else None
