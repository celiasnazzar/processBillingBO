"""
Decide si una proforma extraída se registra como cobro o como incidencia de ingesta
(plan director #3305, §7.4 y §7.7). n8n solo mira resultado_extraccion.

Orden: not_a_proforma -> missing_required_data -> invalid_email.
unreadable_pdf se decide antes de extraer (main.py).
Los detalles no llevan datos personales: van a la BD y al portal.
"""
from typing import List
from models.data import ExtractResponse

# Obligatorios que salen del PDF, con su nombre en la BD. fecha_solicitud la pone n8n.
CAMPOS_OBLIGATORIOS = (
    ("num_pedido", "Numero_de_pedido"),
    ("num_proforma", "Numero_proforma"),
    ("codigo_cliente", "Codigo_de_cliente"),
    ("nombre_cliente", "Nombre_de_cliente"),
    ("importe_proforma", "Importe"),
)

DETALLE_EMAIL = {
    ("", "bd_sin_email"): "El PDF no trae email y el pedido no tiene email válido en la BD de clientes.",
    ("", "bd_no_disponible"): "El PDF no trae email y no se ha podido consultar la BD de clientes.",
    ("x", "bd_sin_email"): "El email del PDF está incompleto o no es válido y el pedido no tiene email válido en la BD de clientes.",
    ("x", "bd_no_disponible"): "El email del PDF está incompleto o no es válido y no se ha podido consultar la BD de clientes.",
}

def incidencia(data: ExtractResponse, motivo: str, detalle: str) -> ExtractResponse:
    data.resultado_extraccion = "incidencia"
    data.motivo_ingesta_incidencia = motivo
    data.detalle_ingesta_incidencia = detalle[:1000]
    return data

def campos_faltantes(data: ExtractResponse) -> List[str]:
    faltan = []
    for campo_bd, atributo in CAMPOS_OBLIGATORIOS:
        valor = getattr(data, atributo)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            faltan.append(campo_bd)
    # El procedimiento rechaza importes negativos
    if data.Importe is not None and data.Importe < 0 and "importe_proforma" not in faltan:
        faltan.append("importe_proforma")
    return faltan

def decidir_ingesta(data: ExtractResponse, es_proforma: bool) -> ExtractResponse:
    if not es_proforma:
        return incidencia(data, "not_a_proforma",
                          "El documento no lleva la etiqueta de proforma (posible factura o justificante).")

    data.campos_faltantes = campos_faltantes(data)
    if data.campos_faltantes:
        return incidencia(data, "missing_required_data",
                          "Faltan datos obligatorios: " + ", ".join(data.campos_faltantes) + ".")

    if not data.email_cliente.strip():
        clave = ("x" if (data.email or "").strip() else "", data.motivo_email)
        detalle = DETALLE_EMAIL.get(clave, "No hay un email de cliente utilizable.")
        return incidencia(data, "invalid_email", detalle)

    data.resultado_extraccion = "cobro"
    return data
