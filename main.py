import os, tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from models.data import ExtractResponse
from services.pdfReader import has_text_layer, extract_text_blocks
from services.pdfDataExtraction import extract_fields_from_blocks
# from services.ocr import pdf_to_blocks_via_ocr

app = FastAPI(
    title="Extractor de Proformas/Facturas",
    version="1.2.0",
    description="Sube un PDF y obtén campos clave.",
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract", response_model=ExtractResponse)
async def extract(pdf: UploadFile = File(...)):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Sube un archivo .pdf")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await pdf.read())
        path = tmp.name

    try:
        if has_text_layer(path):
            blocks = extract_text_blocks(path)
        # else:
        #     blocks = pdf_to_blocks_via_ocr(path)

        data = extract_fields_from_blocks(blocks)
        return JSONResponse(data.dict())
    finally:
        try: os.remove(path)
        except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8000, reload=True)
