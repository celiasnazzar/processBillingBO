from enum import Enum
from pydantic import BaseModel
from typing import Tuple

class Block(BaseModel):
    text: str
    bbox: Tuple[float, float, float, float]
    font: float = 10.0
    page: int = 0

class ExtractResponse(BaseModel):
    Numero_proforma: str
    Fecha_de_la_factura: str
    Numero_de_pedido: str
    Referencia_de_pedido: str
    
    Nombre_de_cliente: str
    Importe: str
    Moneda: str | None = None
    Unidades: str | None = 0

    confidence: float
    source: str
    pais: str | None = None
    telefono: str | None = None
    email: str | None = None

class mailInput(BaseModel):
    idioma: str
    importe: float
    moneda: str
    numeroPedido: int
    fechaFactura: str

class mailOutput(BaseModel):
    email_body: str
    email_subject: str