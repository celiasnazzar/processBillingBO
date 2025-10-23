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
    Unidades: int | None = 0

    Envio_bloque: str | None = ""
    confidence: float
    source: str   
    
