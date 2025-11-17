import copy
from io import BytesIO
from fastapi import HTTPException
import pandas as pd
from openpyxl import load_workbook
from copy import copy


def insertData(data: dict, content: bytes) -> bytes:
    """Añade una nueva fila al Excel manteniendo el formato original"""
    
    try:
        # Leer con pandas para validar columnas
        df = pd.read_excel(BytesIO(content), sheet_name="Tabla1", header=2)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer la hoja: {exc}")
    
    missing_cols = set(data.keys()) - set(df.columns)
    if missing_cols:
        raise HTTPException(
            status_code=400,
            detail=f"Columnas no encontradas: {missing_cols}. Disponibles: {list(df.columns)}"
        )
    
    # Cargar el workbook original con openpyxl (mantiene formato)
    wb = load_workbook(BytesIO(content))
    ws = wb["Tabla1"]
    
    # Encontrar la primera fila vacía (después del header en fila 3)
    # Header está en fila 3 (índice 3), datos empiezan en fila 4
    next_row = ws.max_row + 1
    
    # Obtener el orden de las columnas del header (fila 3)
    header_row = 3
    column_names = []
    for cell in ws[header_row]:
        if cell.value:
            column_names.append(str(cell.value).strip())
        else:
            column_names.append(None)
    
    # Insertar los datos en el orden correcto    
    for col_idx, col_name in enumerate(column_names, start=1):
        if col_name and col_name in data:
            cell = ws.cell(row=next_row, column=col_idx)
            cell.value = data[col_name]
            
            # Copiar el estilo de la celda superior (sin métodos deprecados)
            if next_row > header_row + 1:
                source_cell = ws.cell(row=next_row - 1, column=col_idx)
                if source_cell.has_style:
                    cell.font = copy(source_cell.font)
                    cell.border = copy(source_cell.border)
                    cell.fill = copy(source_cell.fill)
                    cell.number_format = source_cell.number_format
                    cell.alignment = copy(source_cell.alignment)
    
    # Guardar en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return output.getvalue()