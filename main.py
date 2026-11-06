from datetime import date
import os, tempfile, traceback
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from langdetect import detect, DetectorFactory

from services.excelReading.insertData import insertData
from services.excelReading.excelDuplicates import find_duplicates
from services.pdfReading.pdfReader import has_text_layer, extract_text_blocks
from services.pdfReading.pdfDataExtraction import extract_fields_from_blocks, is_proforma
from services.mail.generateBody import generateBody
from services.mail.correctCustomerEmail import correctCustomerEmail
from services.ingesta.decision import decidir_ingesta, incidencia

from models.data import ExtractResponse, mailInput, mailOutput, correctEmailInput, correctEmailOutput

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
    """
    Recibe un PDF, extrae los campos (solo texto embebido, sin OCR) y decide la ingesta.

    Siempre HTTP 200 con resultado_extraccion:
      - cobro: registrar con p_ingesta_registrar_cobro.
      - incidencia: registrar con p_ingesta_registrar_incidencia usando motivo_ingesta_incidencia,
        detalle_ingesta_incidencia y la respuesta completa como datos_extraidos.
    Un 5xx es un fallo técnico: n8n reintenta (plan director §7.4.1).
    """
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    content = await pdf.read()
    if not content:
        return incidencia(ExtractResponse(), "unreadable_pdf", "El fichero PDF está vacío.")

    tmp_path = None
    try:
        # Guardar PDF temporalmente
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(content)

        # --- Solo lectura de texto, sin OCR ---
        try:
            blocks = extract_text_blocks(tmp_path)
        except Exception as e:
            # PDF corrupto o protegido: reintentar no lo arregla
            traceback.print_exc()
            return incidencia(ExtractResponse(), "unreadable_pdf",
                              f"No se ha podido abrir el PDF: {type(e).__name__}.")

        if not blocks:
            return incidencia(ExtractResponse(), "unreadable_pdf",
                              "El PDF no tiene texto (escaneado o imagen).")

        # Procesar campos
        data = extract_fields_from_blocks(blocks)
        es_proforma = is_proforma(blocks)

        # Email del PDF vacío o no válido (p. ej. cortado): se busca en la BD de clientes por nº de pedido
        if es_proforma and not data.es_email_pdf_valido:
            correccion = correctCustomerEmail(data.Numero_de_pedido, data.email)
            data.email_cliente = correccion.email_cliente
            data.es_email_corregido = correccion.es_email_corregido
            data.email_pdf_cliente = correccion.email_pdf_cliente
            data.motivo_email = correccion.motivo

        data = decidir_ingesta(data, es_proforma)
        print(f"DECISIÓN: {data.resultado_extraccion} {data.motivo_ingesta_incidencia or ''} "
              f"{data.detalle_ingesta_incidencia or ''}".rstrip())
        return data

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

@app.post("/correct-customer-email", response_model=correctEmailOutput)
def correct_customer_email(input: correctEmailInput):
    """Corrige el email del PDF con el de la BD de clientes. /extract ya lo aplica; se mantiene para uso aparte."""
    return correctCustomerEmail(input.num_pedido, input.email_pdf)

@app.post("/processExcel")
async def process_excel(
    numPedido: int | None = Form(None),
    numProforma: int | None = Form(None),
    fechaFact: date | None = Form(None),
    refPedido: str | None = Form(None),
    nomCliente: str | None = Form(None),
    importe: float | None = Form(None),
    uds: int | None = Form(None),
    pais: str | None = Form(None),
    email: str | None = Form(None),

    backOffice: str | None = Form(None),
    idioma: str | None = Form(None),
    fechaSolicitud: date | None = Form(None),
    estado: str | None = Form("Pendiente"),

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
    
    # Permitir valores nulos en las fechas/otros campos
    dateFact = fechaFact.strftime("%d/%m/%Y") if fechaFact else None
    dateSolicitud = fechaSolicitud.strftime("%d/%m/%Y") if fechaSolicitud else None
    
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
        return JSONResponse(
            status_code=200,
            content={
                "duplicado": "true",  
                "message": "Registro ya existe en el archivo Excel",
                "data": data,
            },
            headers={
                "X-DUPLICADO": "true"  
            }
        )
    
    # Insertar nueva fila
    try:
        print("Insertando nuevos datos en el archivo Excel...")
        newContent = insertData(data, content)
        print("Datos insertados correctamente.")
        # Devolver el archivo Excel actualizado
        return Response(
            content=newContent,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=updated_{file.filename}",
                "X-DUPLICADO": "false"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al insertar datos: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8000, reload=True)
