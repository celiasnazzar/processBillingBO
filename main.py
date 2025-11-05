import os, tempfile, traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from langdetect import detect, DetectorFactory

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
async def detect_language(string: str):
    """Detecta el idioma del texto proporcionado."""
    DetectorFactory.seed = 0  
    try:
        lang = detect(string)
        return {"language": lang}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detectando idioma: {e}")

@app.post("/generateMail", response_model=mailOutput)
async def generate_mail(input: mailInput):
    """Genera un correo electrónico de solicitud de pago basado en los datos proporcionados."""
    try:
        body, subject = generateBody(input.idioma, input.importe, input.moneda, input.numeroPedido, input.fechaFactura)
        return {"email_body": body, "email_subject": subject}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando correo: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8000, reload=True)
