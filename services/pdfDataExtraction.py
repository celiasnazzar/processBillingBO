import re, math, unicodedata
from typing import List, Optional, Tuple, Dict
from dateutil import parser as dtp
from models.data import Block, ExtractResponse
from settings import settings

# --- regex y anchors ---
PROFORMA_LABEL = r'(?:pro[\s\-]?forma(?:\s*invoice)?|factura\s*proforma|fattura\s*proforma)'
ORDER_LABEL    = r'(?:order|Nº ORDINE|N. COMMANDE|pedido|ORDER N.)'
NUM_LABEL      = r'(?:n[ºo\.]*|no\.?|num\.?|number|#)'

RX_ID_GENERIC       = re.compile(r'\b[A-Z0-9][A-Z0-9\-\/\.]{4,}\b')
RX_REF_YYYY_SLASH   = re.compile(r'\b(20\d{2}\/\d{3,7})\b')
RX_MONEY            = re.compile(r'(?:EUR|€)?\s?\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})|(?:EUR|€)\s?\d+[.,]\d{2}')
RX_DATE             = re.compile(r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b')
RX_UPPER_LINE       = re.compile(r'^[A-Z0-9 .,&\'\-]{3,70}$')
ANCH_PROFORMA = re.compile(
    r'\b(?:pro[\s\-]?forma(?:\s*invoice)?|factura\s*proforma|fattura\s*proforma)\b'
    r'(?:\s*(?:n[º°o\.]*|no\.?|num\.?|number|#))?',
    re.I
)
ANCH_ORDER          = re.compile(fr'\b{ORDER_LABEL}\b\s',   re.I)
ANCH_TOTAL          = re.compile(r'\bTOTAL(?:E)?\b', re.I)
ANCH_DATE           = re.compile(r'\b(fecha|date|data)\b', re.I)
ANCH_DELIVERY       = re.compile(r'INDIRIZZO DI CONSEGNA', re.I)
TOTAL_RX            = re.compile(r'\bTOTAL(?:E)?\b', re.I)
UNIT_WORD_RX        = re.compile(r'\b(UND|UNIDAD(?:ES)?|PCS|PZ|PCE)\b', re.I)
UNIT_NUM_RX         = re.compile(r'(\d{1,7})(?:[.,]\d+)?\s*(?:UND|UNIDAD(?:ES)?|PCS|PZ|PCE)\b', re.I)
RX_ID_TOKEN         = re.compile(r'\b([A-Z]*\d{3,}|[A-Z0-9][A-Z0-9\-\/\.]{1,})\b')
_ID                 = r'([A-Z]?\d[\w\-\/\.]{2,}|[A-Z0-9][A-Z0-9\-\/\.]{3,})'
RX_EMAIL = re.compile(r'([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})', re.I)
RX_PHONE = re.compile(r'(\+?\d[\d\s\-\(\)\.]{7,})')
HDR_SHIP = re.compile(
    r'\b(?:GOODS\s+DELIVERY\s+ADDRESS|DELIVERY\s+ADDRESS|ADRESSE\s+LIVRAISON|'
    r'DIRECCIÓN\s+DE\s+ENTREGA|INDIRIZZO\s+DI\s+CONSEGNA)\b', re.I)

COUNTRIES = [
    r'ESPAÑA|SPAIN', r'ITALIA|ITALY', r'FRANCIA|FRANCE', r'PORTUGAL',
    r'RUMANIA|ROMANIA|ROUMANIE', r'GERMANY|ALEMANIA|ALLEMAGNE',
    r'GREECE|GRECIA|GRÈCE', r'POLAND|POLONIA|POLOGNE'
]
RX_COUNTRY = re.compile(r'\b(?:' + '|'.join(COUNTRIES) + r')\b', re.I)
HEADERS = [
    "GOODS DELIVERY ADDRESS",
    "ADRESSE LIVRAISON",
    "INDIRIZZO DI CONSEGNA",
    "DIRECCIÓN ENVÍO MERCANCÍA",
    "DIRECCION ENVIO MERCANCIA",   # sin acentos (por si el OCR los pierde)
    "LIEFERADRESSE",
]


# --- helpers ---
def _norm_text(s: str) -> str:
    s = unicodedata.normalize('NFKC', s).replace('\xa0', ' ')
    s = s.replace('°', 'º')
    s = re.sub(r'[ \t]+', ' ', s)
    return s

def _deaccent(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

HEADER_RX = re.compile(
    r'(?:' + '|'.join([re.sub(r'\s+', r'\\s+', _deaccent(h)) for h in HEADERS]) + r')',
    re.I
)

def _norm(s: str) -> str:
    s = s.replace('\xa0', ' ')                 
    s = _deaccent(s)
    s = re.sub(r'\s+', ' ', s)                 
    return s.strip()


def normalize_phone(raw: str) -> str:
    raw = raw.strip()
    plus = '+' if raw.strip().startswith('+') else ''
    digits = re.sub(r'\D', '', raw)
    return plus + digits if digits else ''

def get_shipping_panel_blocks(blocks: List[Block]) -> List[Block]:
    """Devuelve los bloques del panel de envío (derecha) usando el encabezado como frontera."""
    headers = [b for b in blocks if HDR_SHIP.search(b.text)]
    if not headers:
        return []
    hdr = sorted(headers, key=lambda b: (b.page, b.bbox[1]))[0]
    split_x = hdr.bbox[0]
    return [b for b in blocks if b.page == hdr.page and b.bbox[0] >= split_x - 5]

def shipping_name_from_header_v2(lines: List[str]) -> str:
    """
    Busca el encabezado de envío en 'lines' (tolerante a acentos/espacios).
    - Si hay texto en la MISMA línea a la derecha → lo devuelve.
    - Si no, devuelve la PRIMERA línea no vacía posterior.
    """
    for i, raw in enumerate(lines):
        raw_strip = raw.strip()
        norm_line = _norm(raw_strip)
        m = HEADER_RX.search(norm_line)
        if not m:
            continue

        tail_norm = norm_line[m.end():].strip()
        if tail_norm:
            header_pat = re.compile(
                r'(?:' + '|'.join([re.sub(r'\s+', r'\\s+', h) for h in HEADERS]) + r')\s*',
                re.I
            )
            m2 = header_pat.search(raw_strip)
            if m2:
                return raw_strip[m2.end():].strip()
            return tail_norm

        for j in range(i + 1, len(lines)):
            nxt = lines[j].strip()
            if nxt:
                return nxt
        return ""

    return ""

def lines_from_blocks(panel: List[Block]) -> List[str]:
    """Agrupa por fila visual y devuelve líneas ordenadas de arriba a abajo."""
    if not panel:
        return []

    def y_overlap(a, b):
        y0, y1 = a[1], a[3]; a0, a1 = b[1], b[3]
        inter = max(0, min(y1, a1) - max(y0, a0))
        denom = max((y1 - y0), (a1 - a0), 1e-6)
        return inter / denom
    panel = sorted(panel, key=lambda b: (b.bbox[1], b.bbox[0]))
    lines = []
    for b in panel:
        placed = False
        for L in lines:
            if y_overlap(b.bbox, L[0].bbox) >= 0.55:
                L.append(b); placed = True; break
        if not placed:
            lines.append([b])

    out = []
    for L in lines:
        L.sort(key=lambda x: x.bbox[0])
        out.append(" ".join(x.text.strip() for x in L).strip())
    return out

def extract_shipping_fields_from_text(lines: List[str]) -> Dict[str, str]:
    """
    Espera líneas del panel de envío. Heurísticas:
    - nombre: primera línea no vacía que NO sea 'TEL/Email' ni empiece por código postal
    - país: primer match de RX_COUNTRY (última aparición tiene prioridad)
    - email: primer match RX_EMAIL
    - teléfono: número más largo (prioriza líneas con 'TEL')
    """
    name = ""
    country = ""
    email = ""
    phone = ""

    # 1) email
    for ln in lines:
        m = RX_EMAIL.search(ln)
        if m:
            email = m.group(1).lower()
            break

    # 2) teléfono (prioriza línea con 'TEL')
    phone_candidates = []
    for ln in lines:
        if 'TEL' in ln.upper() or 'PHONE' in ln.upper():
            phone_candidates.append(ln)
    phone_candidates += lines  # fallback
    best = ""
    for ln in phone_candidates:
        for m in RX_PHONE.finditer(ln):
            cand = normalize_phone(m.group(1))
            if len(cand) > len(best):
                best = cand
    phone = best

    # 3) país (última aparición)
    for ln in lines:
        for m in RX_COUNTRY.finditer(ln):
            country = m.group(0).upper()
    # homogeniza algunas variantes
    country = (country
               .replace('FRANCE', 'FRANCIA')
               .replace('ITALY', 'ITALIA')
               .replace('SPAIN', 'ESPAÑA')
               .replace('ROUMANIE', 'RUMANIA'))

    # 4) nombre (primera línea “tipo nombre”)
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.upper().startswith(('TEL', 'EMAIL', 'ADRESSE', 'ADDRESS', 'DIRECCIÓN', 'INDIRIZZO')):
            continue
        if any(tok in s.upper() for tok in ('CP', 'C.P.', 'ZIP', 'BP ')):
            continue
        # evita que coja líneas que son solo país
        if RX_COUNTRY.fullmatch(s):
            continue
        name = s
        break

    if "\n" in name:
        name = name.split("\n")[0].strip()

    return {
        "Envio_Nombre": name,
        "Envio_Pais": country,
        "Envio_Telefono": phone,
        "Envio_Email": email,
    }

def extract_shipping_fields(blocks: List[Block]) -> Dict[str, str]:
    panel = get_shipping_panel_blocks(blocks)
    lines = lines_from_blocks(panel)
    nombre = shipping_name_from_header_v2(lines)

    fields = extract_shipping_fields_from_text(lines)
           
    return fields

def cleanup_amount(raw: str) -> str:
    if not raw: return ""
    s = raw.replace("EUR","").replace("€","").replace("\n"," ").strip()
    s = s.replace(" ", "")
    if "," in s and s.count(",")==1 and s.rsplit(",",1)[1].isdigit():
        s = s.replace(".","").replace(",",".")
    return re.sub(r"[^0-9.]", "", s)

def parse_date(s: str) -> str:
    try:    return dtp.parse(s, dayfirst=True, fuzzy=True).date().isoformat()
    except: return ""

def y_overlap_ratio(b1, b2):
    # ratio de solape vertical entre dos bboxes
    y0, y1 = b1.bbox[1], b1.bbox[3]
    a0, a1 = b2.bbox[1], b2.bbox[3]
    inter = max(0, min(y1, a1) - max(y0, a0))
    denom = max((y1 - y0), (a1 - a0), 1e-6)
    return inter / denom

def same_line_right_value(anchor_rx, blocks: List[Block], max_dx: int | None = None) -> Optional[str]:
    if max_dx is None:
        max_dx = settings.MAX_RIGHT_DX

    # 1) bloque con el anchor
    cand = [b for b in blocks if re.search(anchor_rx, b.text)]
    if not cand:
        return None
    base = cand[0]
    x0, y0, x1, y1 = base.bbox

    # 2) mismo bloque, justo tras el anchor
    pattern_inline = anchor_rx.pattern + r'(?:\s*(?:[:\-\.·])?\s*([A-Z0-9][A-Z0-9\-\/\.]{0,}))'
    mline = re.search(pattern_inline, base.text, re.I)
    if mline and mline.group(1):
        val = mline.group(1).strip()
        if re.fullmatch(r'\d{1,6}|[A-Z0-9\-\/\.]{2,}', val):
            return val


    # 3) bloques a la derecha con solape vertical suficiente
    window_right = [
        b for b in blocks
        if b.page == base.page
        and b.bbox[0] > x1
        and (b.bbox[0] - x1) <= max_dx
        and y_overlap_ratio(b, base) >= 0.6
    ]
    # prioriza: más a la derecha y solape mayor
    window_right.sort(key=lambda b: (-b.bbox[0], -y_overlap_ratio(b, base)))

    for r in window_right:
        m = RX_ID_TOKEN.search(r.text)
        if m and m.group(1):
            return m.group(1).strip()

    # 4) Ampliar ventana horizontal
    window_right2 = [
        b for b in blocks
        if b.page == base.page
        and b.bbox[0] > x1
        and (b.bbox[0] - x1) <= max_dx * 2
        and y_overlap_ratio(b, base) >= 0.4
    ]
    window_right2.sort(key=lambda b: (-b.bbox[0], -y_overlap_ratio(b, base)))
    for r in window_right2:
        m = RX_ID_TOKEN.search(r.text)
        if m and m.group(1):
            return m.group(1).strip()

    return None


# --- Busca el bloque con la información de las unidades vendidas ---
def findUnits(blocks: List[Block]) -> int:
    if not blocks:
        return 0

    candidates = [b for b in blocks if UNIT_WORD_RX.search(b.text)]

    if candidates:
        # Prioriza: (a) contenga TOTAL, (b) más abajo en página, (c) más a la derecha
        candidates.sort(
            key=lambda b: (
                0 if TOTAL_RX.search(b.text) else 1,
                -b.bbox[1],           
                b.bbox[0]              
            )
        )
        for b in candidates:
            nums = []
            for m in UNIT_NUM_RX.finditer(b.text):
                raw = m.group(1).replace('.', '').replace(',', '.')
                try:
                    nums.append(int(round(float(raw))))
                except:
                    pass
            if nums:
                return nums[-1]

    # --- Fallback: suma todas las apariciones en todas las líneas ---
    total, seen = 0, 0
    for b in blocks:
        for m in UNIT_NUM_RX.finditer(b.text):
            raw = m.group(1).replace('.', '').replace(',', '.')
            try:
                total += int(round(float(raw)))
                seen += 1
            except:
                pass
    return total if seen > 0 else 0

# --- Busca el Nº de pedido en todo el texto plano ---
def find_order_number(blocks) -> str:
    """
    Busca el Nº de pedido en texto plano, cubriendo:
    - 'Nº ORDINE 284128'  /  'N. COMMANDE 349911'  /  'ORDER N. 261378'
    - 'ORDINE 284128' (sin 'N.')
    - etiqueta y número separados por salto de línea (1–2 líneas)
    """
    txt = _norm_text("\n".join(b.text for b in blocks))
    lines = [l.strip() for l in txt.splitlines() if l.strip()]

    LABEL = r'(?:ORDINE|ORDER|COMMANDE|PEDIDO|ORDEN)'
    NLAB  = r'(?:N[ºO\.]*|NO\.?|NUM\.?|NUMBER|#)?'
    SEP   = r'[\s:\-·\.]*'                         

    m = re.search(rf'\b{NLAB}\s*{LABEL}\b{SEP}{_ID}', txt, re.I)
    if m:
        return m.group(1)

    m = re.search(rf'\b{LABEL}\b{SEP}{NLAB}?{SEP}{_ID}', txt, re.I)
    if m:
        return m.group(1)

    lab_rx = re.compile(rf'\b{LABEL}\b', re.I)
    id_rx  = re.compile(rf'^{SEP}{_ID}', re.I) 
    for i, ln in enumerate(lines):
        if lab_rx.search(ln):
            # mismo renglón
            mm = re.search(_ID, ln, re.I)
            if mm:
                return mm.group(1)
            for j in range(i+1, min(i+3, len(lines))):
                mm2 = id_rx.search(lines[j])
                if mm2:
                    return mm2.group(1)

    return ""

# ---- helpers para agrupar por "fila visual" -----------------
def _y_overlap(a: Tuple[float,float,float,float], b: Tuple[float,float,float,float]) -> float:
    y0, y1 = a[1], a[3]
    a0, a1 = b[1], b[3]
    inter = max(0, min(y1, a1) - max(y0, a0))
    denom = max((y1 - y0), (a1 - a0), 1e-6)
    return inter / denom

# --- agrupa bloques en filas visuales ---
def _build_lines(blocks: List[Block], overlap_min: float = 0.55) -> List[List[Block]]:
    """Agrupa bloques en filas por solape vertical; cada fila = lista de bloques ordenados por X."""
    if not blocks: 
        return []

    bs = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    lines: List[List[Block]] = []
    for b in bs:
        placed = False
        for L in lines:
            if _y_overlap(b.bbox, L[0].bbox) >= overlap_min:
                L.append(b); placed = True; break
        if not placed:
            lines.append([b])

    for L in lines:
        L.sort(key=lambda x: x.bbox[0])
    return lines

LABEL = r'(?:ordine|order|commande|pedido|orden)'
NLAB  = r'(?:n[º°o\.]*|no\.?|num\.?|number|#)?'      
ORDER_TOKEN = re.compile(r'\b([A-Z]?\d{4,9})\b')

def find_order_number_from_lines(blocks: List[Block]) -> str:
    """Detecta Nº de pedido mirando SOLO la misma fila visual que la etiqueta."""
    lines = _build_lines(blocks, overlap_min=0.55)
    # Recorre filas de arriba a abajo
    for L in lines:
        line_text = " ".join(b.text for b in L)
        if re.search(fr'\b{NLAB}\s*{LABEL}\b', line_text, re.I) or re.search(fr'\b{LABEL}\b\s*{NLAB}', line_text, re.I):
            # busca el primer bloque donde aparece la etiqueta
            anchor_idx = None
            for i, b in enumerate(L):
                if re.search(fr'\b{LABEL}\b', b.text, re.I):
                    anchor_idx = i; break
            if anchor_idx is None:
                continue
            # examina bloques a la derecha en la misma línea
            for b in L[anchor_idx+1:]:
                m = ORDER_TOKEN.search(b.text)
                if m:
                    return m.group(1)
            # si no hubo token a la derecha, intenta dentro del mismo bloque
            m_inline = ORDER_TOKEN.search(L[anchor_idx].text)
            if m_inline:
                return m_inline.group(1)

            idx = lines.index(L)
            if idx+1 < len(lines) and _y_overlap(L[0].bbox, lines[idx+1][0].bbox) >= 0.20:
                for b in lines[idx+1]:
                    m2 = ORDER_TOKEN.search(b.text)
                    if m2:
                        return m2.group(1)
    return ""

# --- extractor principal ---
def extract_fields_from_blocks(blocks: List[Block]) -> ExtractResponse:
    text_all = "\n".join(b.text for b in blocks)

    proforma = same_line_right_value(ANCH_PROFORMA, blocks) or ""
    c1 = 0.9 if proforma else 0.0

    pedido = find_order_number_from_lines(blocks)
    if not pedido:
        pedido = find_order_number(blocks)
    c2 = 0.9 if pedido else 0.0


    ref = ""
    mref = RX_REF_YYYY_SLASH.search(text_all)
    if mref: ref, c3 = mref.group(1), 0.9
    else:    ref, c3 = "", 0.0

    # Extrae datos de cliente del panel de envío
    envio_fields = extract_shipping_fields(blocks)

    importe_raw, c5 = "", 0.0
    total_anchor = [b for b in blocks if ANCH_TOTAL.search(b.text)]
    if total_anchor:
        base = total_anchor[0]
        m = re.search(r'\bTOTAL(?:E)?\b.*?(' + RX_MONEY.pattern + r')', base.text, re.I)
        if m: importe_raw, c5 = m.group(1), 0.9
        else:
            neigh = [b for b in blocks if b.page==base.page and abs(b.bbox[1]-base.bbox[1])<40 and b is not base]
            for n in neigh:
                m2 = RX_MONEY.search(n.text)
                if m2: importe_raw, c5 = m2.group(0), 0.85; break
    if not importe_raw:
        cands = []
        for b in blocks:
            for m in RX_MONEY.finditer(b.text):
                raw = m.group(0)
                val = cleanup_amount(raw)
                try: cands.append((float(val or 0), raw))
                except: pass
        if cands:
            cands.sort(key=lambda t: -t[0])
            importe_raw, c5 = cands[0][1], 0.7
    importe = cleanup_amount(importe_raw)

    fecha, c6 = "", 0.0
    date_blocks = [b for b in blocks if ANCH_DATE.search(b.text)]
    if date_blocks:
        base = date_blocks[0]
        md = RX_DATE.search(base.text)
        if md: fecha, c6 = parse_date(md.group(1)), 0.9
        else:
            neigh = [b for b in blocks if b.page==base.page and abs(b.bbox[1]-base.bbox[1])<40 and b is not base]
            for n in neigh:
                md2 = RX_DATE.search(n.text)
                if md2: fecha, c6 = parse_date(md2.group(1)), 0.85; break
    if not fecha:
        md = RX_DATE.search(text_all)
        if md: fecha, c6 = parse_date(md.group(1)), 0.6

    unidades = findUnits(blocks)
    confidence = round((c1+c2+c3+c5+c6)/6, 2)

    return ExtractResponse(
        Numero_de_pedido=pedido,
        Nombre_de_cliente=envio_fields["Envio_Nombre"],
        Numero_proforma=proforma,
        Fecha_de_la_factura=fecha,
        Referencia_de_pedido=ref,
        Importe=importe,
        Unidades=unidades,        
        confidence=confidence,
        source="rule",
        pais=envio_fields["Envio_Pais"],
        telefono=envio_fields["Envio_Telefono"],
        email=envio_fields["Envio_Email"],
    )
