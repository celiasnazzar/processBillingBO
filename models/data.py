from enum import Enum
from pydantic import BaseModel
from typing import Literal, Optional, Tuple

class Block(BaseModel):
    text: str
    bbox: Tuple[float, float, float, float]
    font: float = 10.0
    page: int = 0

class ExtractResponse(BaseModel):
    Numero_proforma: int | None = None
    Fecha_de_la_factura: str
    Numero_de_pedido: int
    Referencia_de_pedido: str
    
    Nombre_de_cliente: str | None = None
    Codigo_de_cliente: int | None = None
    Importe: float | None = None
    Moneda: str | None = None
    Unidades: int | None = 0

    source: str
    pais: str | None = None
    telefono: str | None = None
    email: str | None = None
    es_email_pdf_valido: bool = False
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
    email_bd: Optional[str] = None
    es_corregido: bool
    motivo: Optional[Literal["match", "replaced", "bd_sin_email", "bd_no_disponible"]] = None
    es_email_pdf_valido: bool