import pdfplumber, fitz
from typing import List
from models.data import Block

def has_text_layer(path: str) -> bool:
    try:
        with pdfplumber.open(path) as pdf:
            return any((p.extract_text() or "").strip() for p in pdf.pages)
    except Exception:
        return False

def extract_text_blocks(path: str) -> List[Block]:
    blocks: List[Block] = []
    doc = fitz.open(path)
    for p in doc:
        d = p.get_text("dict")
        for b in d.get("blocks", []):
            if "lines" not in b: 
                continue
            texts, sizes = [], []
            for l in b["lines"]:
                for s in l.get("spans", []):
                    texts.append(s["text"]); sizes.append(s.get("size", 10))
            text = "\n".join(" ".join(t.split()) for t in "\n".join(texts).splitlines()).strip()
            if not text: 
                continue
            x0,y0,x1,y1 = b["bbox"]
            blocks.append(Block(text=text, bbox=(x0,y0,x1,y1), page=p.number,
                                font=(sum(sizes)/len(sizes) if sizes else 10)))
    return blocks
