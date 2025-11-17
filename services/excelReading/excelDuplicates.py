from io import BytesIO
from fastapi import HTTPException
import pandas as pd


def find_duplicates(num_pedido: int, num_proforma: int, content: bytes) -> bool:
    """Verifica si existe un registro duplicado"""
    try:
        df = pd.read_excel(BytesIO(content), sheet_name="Tabla1", header=2)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer la hoja 'Tabla1': {exc}")

    colmap = {c: str(c).strip().upper() for c in df.columns}
    
    pedido_col = None
    proforma_col = None

    for original, norm in colmap.items():
        if "NUMERO DE PEDIDO" in norm and "PROFORMA" not in norm:
            pedido_col = original
        if "NUMERO" in norm and "PROFORMA" in norm:
            proforma_col = original

    if pedido_col is None or proforma_col is None:
        raise HTTPException(
            status_code=400,
            detail=f"No se encontraron las columnas. Columnas: {list(df.columns)}"
        )

    def safe_convert(series):
        return pd.to_numeric(series, errors='coerce').fillna(-1).astype(int).astype(str).str.strip()
    
    serie_pedido = safe_convert(df[pedido_col])
    serie_proforma = safe_convert(df[proforma_col])

    pedido_target = str(int(num_pedido)).strip()
    proforma_target = str(int(num_proforma)).strip()

    mask = (serie_pedido == pedido_target) & (serie_proforma == proforma_target)
    return bool(mask.any())
