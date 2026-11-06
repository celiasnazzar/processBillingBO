from pydantic import BaseModel
from typing import Literal, Optional, Tuple

class Block(BaseModel):
    text: str
    bbox: Tuple[float, float, float, float]
    font: float = 10.0
    page: int = 0

MotivoEmail = Literal["match", "replaced", "bd_sin_email", "bd_no_disponible"]
MotivoIncidencia = Literal["unreadable_pdf", "not_a_proforma", "missing_required_data", "invalid_email"]

class ExtractResponse(BaseModel):
    # --- Decisión de ingesta: n8n solo mira resultado_extraccion ---
    # cobro: llamar a p_ingesta_registrar_cobro. incidencia: llamar a p_ingesta_registrar_incidencia
    # con motivo_ingesta_incidencia, detalle_ingesta_incidencia y esta respuesta como datos_extraidos.
    resultado_extraccion: Literal["cobro", "incidencia"] = "cobro"
    motivo_ingesta_incidencia: Optional[MotivoIncidencia] = None
    # Sin datos personales (va a la BD y al portal)
    detalle_ingesta_incidencia: str | None = None
    # Obligatorios que no se han podido leer, con el nombre del campo en la BD
    campos_faltantes: list[str] = []

    # Todos opcionales: si falta un dato se devuelve incidencia, no un error 500
    Numero_proforma: int | None = None
    Fecha_de_la_factura: str = ""
    Numero_de_pedido: int | None = None
    Referencia_de_pedido: str = ""

    Nombre_de_cliente: str | None = None
    Codigo_de_cliente: str | None = None
    Importe: float | None = None
    Moneda: str | None = None
    Unidades: int | None = 0

    source: str = "rule"
    pais: str | None = None
    telefono: str | None = None
    email: str | None = None
    es_email_pdf_valido: bool = False
    # Campos para /ingesta/cobros. Si el email del PDF falta o no es válido, /extract lo busca en la BD de clientes
    email_cliente: str = ""
    es_email_corregido: int = 0
    # Email tal como venía en el PDF; solo con es_email_corregido = 1. null si el PDF no traía email
    email_pdf_cliente: str | None = None
    # match | replaced | bd_sin_email | bd_no_disponible (None si no se consulta la BD)
    motivo_email: Optional[MotivoEmail] = None
    agente: str | None = None

class mailInput(BaseModel):
    idioma: Optional[str] | None = "en"
    importe: Optional[float] = None
    moneda: Optional[str] = None
    numeroPedido: Optional[int] = None
    fechaFactura: Optional[str] = None

class mailOutput(BaseModel):
    email_body: str
    email_subject: str

class correctEmailInput(BaseModel):
    num_pedido: int
    email_pdf: Optional[str] = ""

class correctEmailOutput(BaseModel):
    email_aplicado: str
    email_bd: str = ""
    es_corregido: bool
    motivo: Optional[MotivoEmail] = None
    es_email_pdf_valido: bool
    # Campos para /ingesta/cobros
    email_cliente: str
    es_email_corregido: int
    email_pdf_cliente: str | None = None