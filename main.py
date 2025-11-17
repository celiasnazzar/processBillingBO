from datetime import date
from gettext import find
import os, tempfile, traceback
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from langdetect import detect, DetectorFactory

from services.excelReading.insertData import insertData
from services.excelReading.excelDuplicates import find_duplicates
from services.pdfReading.pdfReader import has_text_layer, extract_text_blocks
from services.pdfReading.pdfDataExtraction import extract_fields_from_blocks
from services.mail.generateBody import generateBody

from models.data import ExtractResponse, mailInput, mailOutput

app = FastAPI(
    title="Extractor de Proformas/Facturas",
    version="1.2.0",
    description="Sube un PDF y obtén campos clave.",
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract(pdf: UploadFile = File(...)):
    """Recibe un PDF y extrae los campos sin usar OCR (solo texto embebido)."""
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    content = await pdf.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    tmp_path = None
    try:
        # Guardar PDF temporalmente
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(content)

        # --- Solo lectura de texto, sin OCR ---
        try:
            blocks = extract_text_blocks(tmp_path)  # tu función actual
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error leyendo PDF: {e}")

        if not blocks:
            raise HTTPException(status_code=422, detail="No se detectó texto en el PDF")

        # Procesar campos
        data = extract_fields_from_blocks(blocks)
        return JSONResponse(content=data.model_dump())

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass

@app.post("/detect-language")
async def detect_language(string: str | None = ""):
    """Detecta el idioma del texto proporcionado."""
    DetectorFactory.seed = 0

    if not string or not string.strip():
        return {"language": ""}

    try:
        lang = detect(string)
        return {"language": lang}
    except Exception:
        return {"language": ""}

@app.post("/generateMail", response_model=mailOutput)
async def generate_mail(input: mailInput):
    """Genera un correo electrónico de solicitud de pago basado en los datos proporcionados."""
    try:
        # Comprobaciones por si los datos vienen vacíos o con otro formato.
        lang = (input.idioma or "en").lower()
        amount = 0.0 if input.importe is None else float(input.importe)
        currency = input.moneda or ""
        order_no = 0 if input.numeroPedido is None else int(input.numeroPedido)
        date_iso = input.fechaFactura or ""   

        body, subject = generateBody(lang, amount, currency, order_no, date_iso)
        return {"email_body": body, "email_subject": subject}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando correo: {e}")

@app.post("/processExcel")
async def process_excel(
    numPedido: int = Form(...),
    numProforma: int = Form(...),
    fechaFact: date = Form(...),
    refPedido: str = Form(...),
    nomCliente: str = Form(...),
    importe: float = Form(...),
    uds: int = Form(...),
    pais: str = Form(...),
    email: str = Form(...),

    backOffice: str = Form(...),
    idioma: str = Form(...),
    fechaSolicitud: date = Form(...),
    estado: str = Form("Pendiente"),

    file: UploadFile = File(...)
):
    """
    Procesa un archivo Excel:
    1. Verifica si el registro ya existe (duplicado)
    2. Si no existe, añade la nueva fila
    3. Devuelve el Excel actualizado
    """
    
    # Validar tipo de archivo
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx o .xls)")

    # Leer contenido del archivo
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    
    dateFact = fechaFact.strftime("%d/%m/%Y")
    dateSolicitud = fechaSolicitud.strftime("%d/%m/%Y")
    
    data = {
        "NUMERO PROFORMA": numProforma,
        "FECHA FACTURA": dateFact,
        "FECHA SOLICITUD": dateSolicitud,
        "ESTADO": estado,
        "NUMERO DE PEDIDO": numPedido,
        "REFERENCIA PEDIDO": refPedido,
        "NOMBRE DE CLIENTE": nomCliente,
        "IMPORTE": importe,
        "CANTIDAD": uds,
        "PAIS": pais,
        "CORREO CLIENTE": email,
        "BACKOFFICE": backOffice,
        "IDIOMA 2": idioma
    }

    # Verificar duplicados
    duplicado = find_duplicates(numPedido, numProforma, content) 
    
    if duplicado:
        print("Registro duplicado detectado.")
        return {
            "duplicado": "True",
            "message": "Registro ya existe en el archivo Excel",
            "data": data
        }
    
    # Insertar nueva fila
    try:
        newContent = insertData(data, content)
        print("Datos insertados correctamente.")
        # Devolver el archivo Excel actualizado
        return Response(
            content=newContent,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=updated_{file.filename}",
                "duplicado": "False"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al insertar datos: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8000, reload=True)
