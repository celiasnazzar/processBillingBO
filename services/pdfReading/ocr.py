# import io, shutil, subprocess
# from typing import List
# from PIL import Image
# import fitz
# from models.data import Block
# from settings import settings
# from doctr.io import DocumentFile
# from doctr.models import ocr_predictor

# def doctr_pdf_to_blocks(path: str) -> List[Block]:

#     predictor = ocr_predictor(pretrained=True)
#     doc = DocumentFile.from_pdf(path)
#     res = predictor(doc).export()
#     blocks: List[Block] = []
#     for p_idx, page in enumerate(res["pages"]):
#         pw, ph = page.get("dimensions", [1,1])
#         for block in page.get("blocks", []):
#             for line in block.get("lines", []):
#                 words = line.get("words", [])
#                 if not words: 
#                     continue
#                 text = " ".join(w.get("value","") for w in words).strip()
#                 if not text: 
#                     continue
#                 xs, ys, xe, ye = [], [], [], []
#                 for w in words:
#                     (x0,y0),(x1,y1) = w.get("geometry", [[0,0],[1,1]])
#                     xs.append(x0*pw); ys.append(y0*ph); xe.append(x1*pw); ye.append(y1*ph)
#                 blocks.append(Block(text=text, bbox=(min(xs),min(ys),max(xe),max(ye)), page=p_idx))
#     return blocks

# # --- OCRmyPDF (opcional) ---
# def ocrmypdf_available() -> bool:
#     return shutil.which("ocrmypdf") is not None

# def ocrmypdf_pdf_to_blocks(path: str) -> List[Block]:
#     from reader import extract_text_blocks
#     out = path + ".ocr.pdf"
#     subprocess.run(["ocrmypdf","--skip-text","--rotate-pages","--deskew","--force-ocr", path, out],
#                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     return extract_text_blocks(out)

# # --- Tesseract (fallback) ---
# def tesseract_available() -> bool:
#     try:
#         import pytesseract  # noqa
#         return True
#     except Exception:
#         return False

# def tesseract_pdf_to_blocks(path: str) -> List[Block]:
#     import pytesseract
#     doc = fitz.open(path)
#     lines = []
#     for i in range(doc.page_count):
#         pix = doc.load_page(i).get_pixmap(dpi=250)
#         img = Image.open(io.BytesIO(pix.tobytes("png")))
#         lines.append(pytesseract.image_to_string(img, lang=settings.OCR_LANGS))
#     text = "\n".join(lines)
#     return [Block(text=text, page=0)]

# # --- Selección en orden de preferencia ---
# def pdf_to_blocks_via_ocr(path: str) -> List[Block]:
#     for name in [s.strip() for s in settings.OCR_BACKENDS.split(",")]:
#         if name == "doctr":
#             try: return doctr_pdf_to_blocks(path)
#             except Exception: pass
#         if name == "ocrmypdf" and ocrmypdf_available():
#             try: return ocrmypdf_pdf_to_blocks(path)
#             except Exception: pass
#         if name == "tesseract" and tesseract_available():
#             try: return tesseract_pdf_to_blocks(path)
#             except Exception: pass
#     raise RuntimeError("No OCR backend available")
