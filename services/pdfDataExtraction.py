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
RX_CURRENCY_TOKEN = re.compile(r'\b(EUR|USD|GBP|EURO|DOLLAR|DÓLAR|POUND)\b|[€$£]', re.I)
RX_MONEY = re.compile(
    r'(?:EUR|USD|GBP|EURO|€|\$|£)?\s?\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})'
    r'|(?:EUR|USD|GBP|EURO|€|\$|£)\s?\d+(?:[.,]\d{2})',
    re.I
)
RX_TOTAL_MAIN   = re.compile(r'\bTOTAL(?:E)?\b', re.I)
RX_TOTAL_BADCTX = re.compile(
    r'\b('
    r'TAX|TAXE|TAXES|TVA|IVA|IGIC|'
    r'IMPUESTOS|IMPOSTOS|IMPOSTI|IMPOSTO|TASSE|TASSA|TAXA'
    r')\b',
    re.I
)
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
UNIT_NUM_RX         = re.compile(
    r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)(?=\s*(?:UND|UNIDAD(?:ES)?|PCS|PZ|PCE)\b)',
    re.I
)

RX_ID_TOKEN         = re.compile(r'\b([A-Z]*\d{3,}|[A-Z0-9][A-Z0-9\-\/\.]{1,})\b')
_ID                 = r'([A-Z]?\d[\w\-\/\.]{2,}|[A-Z0-9][A-Z0-9\-\/\.]{3,})'
RX_EMAIL            = re.compile(r'([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})', re.I)
RX_PHONE            = re.compile(r'(\+?\d[\d\s\-\(\)\.]{7,})')
HDR_SHIP            = re.compile(
    r'\b(?:GOODS\s+DELIVERY\s+ADDRESS|DELIVERY\s+ADDRESS|ADRESSE\s+LIVRAISON|'
    r'DIRECCIÓN\s+DE\s+ENTREGA|INDIRIZZO\s+DI\s+CONSEGNA)\b', re.I)

COUNTRIES = [
    r'ESPAÑA|SPAIN', r'ITALIA|ITALY', r'FRANCIA|FRANCE', r'PORTUGAL',
    r'RUMANIA|ROMANIA|ROUMANIE', r'GERMANY|ALEMANIA|ALLEMAGNE',
    r'GREECE|GRECIA|GRÈCE', r'POLAND|POLONIA|POLOGNE'
]
RX_COUNTRY          = re.compile(r'\b(?:' + '|'.join(COUNTRIES) + r')\b', re.I)
HEADERS = [
    "GOODS DELIVERY ADDRESS",
    "ADRESSE LIVRAISON",
    "INDIRIZZO DI CONSEGNA",
    "DIRECCIÓN ENVÍO MERCANCÍA",
    "DIRECCION ENVIO MERCANCIA",
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

def debug_dump_left_panel(blocks):
    hdr = find_shipping_header_block(blocks)
    print(f"[debug] header_derecho_encontrado={bool(hdr)}")
    if not hdr:
        print("[debug] No se encontró el header de ENVÍO. Revisa HEADER_RX / HEADERS.")
        return

    left_blocks = get_billing_panel_blocks(blocks)
    print(f"[debug] nº_bloques_izquierda={len(left_blocks)} (page={hdr.page})")
    # 1) Líneas agregadas (lo que usa extract_billing_name)
    left_lines = lines_from_blocks(left_blocks)
    print("[debug] LÍNEAS PANEL IZQUIERDO (orden de arriba a abajo):")
    for i, ln in enumerate(left_lines[:30], 1):
        print(f"  {i:02d}. {ln}")

    # 2) (Opcional) Bloques crudos con bbox para ver si hay ruido
    print("[debug] BLOQUES CRUDOS (x0,y0,x1,y1):")
    for b in sorted(left_blocks, key=lambda x: (x.bbox[1], x.bbox[0]))[:50]:
        x0,y0,x1,y1 = map(int, b.bbox)
        print(f"  [{x0:4d},{y0:4d},{x1:4d},{y1:4d}]  {b.text.strip()}")

def debug_pick_billing_name(blocks: List[Block]) -> None:
    panel = get_billing_panel_blocks(blocks)
    lines = lines_from_blocks(panel)
    print("[debug-pick] candidatas panel izq.:")
    for i, ln in enumerate(lines, 1):
        tag = []
        s = ln.strip()
        if EXCLUDE_LEFT_LABELS.search(s): tag.append("EXC_LABEL")
        if EXCLUDE_LEGAL.search(s):       tag.append("EXC_LEGAL")
        if RX_ONLY_COUNTRY.fullmatch(s):  tag.append("ONLY_COUNTRY")
        if RX_DATE.fullmatch(s):          tag.append("ONLY_DATE")
        if re.fullmatch(r'\d{3,}', s):    tag.append("ONLY_NUM")
        first = s.split("\n",1)[0].strip() if "\n" in s else s
        print(f"  {i:02d}. {first}   [{', '.join(tag) or 'ok'}]")


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

def find_shipping_header_block(blocks):
    cands = [b for b in blocks if HEADER_RX.search(_norm(b.text))]
    if not cands:
        return None
    return sorted(cands, key=lambda b: (b.page, b.bbox[1], b.bbox[0]))[0]

def get_shipping_panel_blocks(blocks: List[Block]) -> List[Block]:
    hdr = find_shipping_header_block(blocks)
    if not hdr:
        return []
    split_x = hdr.bbox[0]
    return [b for b in blocks if b.page == hdr.page and b.bbox[0] >= split_x - 5]

def get_billing_panel_blocks(blocks):
    hdr = find_shipping_header_block(blocks)
    if not hdr:
        return []
    split_x = hdr.bbox[0]
    y_min   = hdr.bbox[1] - 6        # margen pequeño por encima del borde del recuadro
    # Opcional: detecta “OBSERVACIONES” para cortar por abajo si existe
    rx_obs  = re.compile(r'\bOBSERVACIONES\b', re.I)
    obs = [b for b in blocks if b.page == hdr.page and rx_obs.search(_norm(b.text))]
    y_max = min([b.bbox[1] for b in obs], default=float('inf'))

    left = [
        b for b in blocks
        if b.page == hdr.page
        and b.bbox[2] <= split_x + 5
        and b.bbox[1] >= y_min
        and b.bbox[1] < y_max
    ]
    return left

RX_LEADING_ORDERNUM = re.compile(r'^\s*\d{3,}\s+(.+)$') 
RX_ONLY_COUNTRY     = re.compile(r'^\s*(?:' + '|'.join(COUNTRIES) + r')\s*$', re.I)
EXCLUDE_LEFT_LABELS = re.compile(
    r'^(?:PROFORMA(?:\s*N[º°o\.]*|(?:\s*N[º°o\.]*)?\.?)?|\s*FECHA\s+PEDIDO|\s*N[º°o\.]*\s*PEDIDO|OBSERVACIONES?)\b',
    re.I
)
EXCLUDE_LEGAL = re.compile(r'Inscrita en Registro mercantil', re.I)

def extract_billing_name(blocks: List[Block]) -> str:
    panel = get_billing_panel_blocks(blocks)
    lines = lines_from_blocks(panel)

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # 1) filtrados duros
        if EXCLUDE_LEFT_LABELS.search(s):     # PROFORMA, FECHA PEDIDO, Nº PEDIDO, OBSERVACIONES
            continue
        if EXCLUDE_LEGAL.search(s):           # texto legal del pie
            continue
        if RX_ONLY_COUNTRY.fullmatch(s):      # solo país
            continue
        if RX_DATE.fullmatch(s):              # solo fecha
            continue
        if re.fullmatch(r'\d{3,}', s):        # solo números
            continue

        # 2) si es un bloque multilínea, quédate con la PRIMERA línea (tu caso real)
        if "\n" in s:
            s = s.split("\n", 1)[0].strip()

        # 3) devuelve la primera línea válida (incluye "21317 ..." tal cual)
        return s

    return ""


# --- Busca el bloque con la información de las unidades vendidas ---
def findUnits(blocks: List[Block]) -> str:
    if not blocks:
        return ""

    candidates = [b for b in blocks if UNIT_WORD_RX.search(b.text)]

    if candidates:
        # Prioriza: (a) contenga TOTAL, (b) más abajo, (c) más a la derecha
        candidates.sort(
            key=lambda b: (
                0 if TOTAL_RX.search(b.text) else 1,
                -b.bbox[1],
                b.bbox[0]
            )
        )
        for b in candidates:
            matches = list(UNIT_NUM_RX.finditer(b.text))
            if matches:
                return matches[-1].group(1).strip()  # número completo

    # --- Fallback: primera coincidencia global ---
    for b in blocks:
        m = UNIT_NUM_RX.search(b.text)
        if m:
            return m.group(1).strip()

    return ""

def detect_currency(text: str) -> str:
    t = text.upper()
    if 'USD' in t or '$' in t:  return 'USD'
    if 'EUR' in t or '€' in t:  return 'EUR'
    if 'GBP' in t or '£' in t:  return 'GBP'
    return ''

# --- Busca el importe total ---
def detect_currency(text: str) -> str:
    t = text.upper()
    if 'USD' in t or '$' in t:  return 'USD'
    if 'EUR' in t or '€' in t:  return 'EUR'
    if 'GBP' in t or '£' in t:  return 'GBP'
    return ''
def find_total_amount(blocks: List[Block]) -> Tuple[str, str, float]:
    # candidatos con "TOTAL" y sin contexto de impuestos
    cands = [b for b in blocks if RX_TOTAL_MAIN.search(b.text) and not RX_TOTAL_BADCTX.search(b.text)]
    if not cands:
        return "", "", 0.0

    def same_row_amount(base: Block):
        # 1) Inline: "TOTAL EUR 1.234,56"
        m_inline = re.search(r'\bTOTAL(?:E)?\b.*?(' + RX_MONEY.pattern + r')', base.text, re.I)
        if m_inline:
            raw = m_inline.group(1)
            cur = detect_currency(base.text) or detect_currency(raw)
            return raw, cur

        # 2) Misma fila visual (a la derecha)
        row = [
            r for r in blocks
            if r.page == base.page
            and r.bbox[0] > base.bbox[2]
            and (r.bbox[0] - base.bbox[2]) <= 600.0
            and y_overlap_ratio(r, base) >= 0.55
        ]
        # prioriza quien tenga token de moneda
        row.sort(key=lambda r: (0 if RX_CURRENCY_TOKEN.search(r.text) else 1,
                                -y_overlap_ratio(r, base),
                                r.bbox[0]))
        for r in row:
            m = RX_MONEY.search(r.text)
            if m:
                raw = m.group(0)
                # moneda: primero base, luego bloque vecino, luego importe
                cur = (detect_currency(base.text)
                       or detect_currency(r.text)
                       or detect_currency(raw))
                return raw, cur

        # 3) Si no hay importe en la misma fila, aborta
        return None, None

    best_zero = None
    # Recorre de ABAJO hacia arriba (el TOTAL final suele ser el más bajo)
    for base in sorted(cands, key=lambda b: (b.page, -b.bbox[1], b.bbox[0])):
        raw, cur = same_row_amount(base)
        if not raw:
            continue
        val = cleanup_amount(raw)
        if val and float(val) > 0.0:
            # si no hay moneda aún, intenta detectarla en toda la página
            if not cur:
                page_text = " ".join(x.text for x in blocks if x.page == base.page)
                cur = detect_currency(page_text)
            return raw, (cur or ''), 0.92
        if best_zero is None:
            # guarda 0,00 por si fuera el único valor
            page_text = " ".join(x.text for x in blocks if x.page == base.page)
            cur = detect_currency(base.text) or detect_currency(page_text) or ''
            best_zero = (raw, cur)

    if best_zero:
        return best_zero[0], best_zero[1], 0.80

    # Fallback: mayor importe global
    mx = []
    for b in blocks:
        for m in RX_MONEY.finditer(b.text):
            try:
                mx.append((float(cleanup_amount(m.group(0)) or 0),
                           m.group(0),
                           detect_currency(b.text) or detect_currency(m.group(0))))
            except:
                pass
    if mx:
        mx.sort(key=lambda t: -t[0])
        return mx[0][1], (mx[0][2] or ''), 0.70

    return "", "", 0.0


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

    # --- Nº de proforma ---
    proforma = same_line_right_value(ANCH_PROFORMA, blocks) or ""
    c1 = 0.9 if proforma else 0.0
    print("N PROFORMA:", proforma)

    #--- Nº de pedido ---
    pedido = find_order_number_from_lines(blocks)
    if not pedido:
        pedido = find_order_number(blocks)
    c2 = 0.9 if pedido else 0.0
    print("N PEDIDO:", pedido)

    #--- Referencia de pedido ---
    ref = ""
    mref = RX_REF_YYYY_SLASH.search(text_all)
    if mref: ref, c3 = mref.group(1), 0.9
    else:    ref, c3 = "", 0.0
    print("REF PEDIDO:", ref)

    # --- Importe total ---
    importe_raw, c5 = "", 0.0
    importe_raw, moneda_iso, c5 = find_total_amount(blocks)
    importe = cleanup_amount(importe_raw or "")
    print("IMPORTE TOTAL:", importe_raw, "->", importe)

    # --- Información del panel de envío ---
    envio_fields = extract_shipping_fields(blocks)
    print("ENVÍO:", envio_fields)

    # --- Información del panel de cliente ---
    nombre_cliente = extract_billing_name(blocks)
    print("NOMBRE CLIENTE:", nombre_cliente)

    # --- Fecha ---
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
    
    print("FECHA:", fecha)

    # --- Unidades ---
    unidades = findUnits(blocks)
    confidence = round((c1+c2+c3+c5+c6)/6, 2)
    print("UNIDADES:", unidades)

    return ExtractResponse(
        Numero_de_pedido=pedido,
        Nombre_de_cliente=nombre_cliente,
        Numero_proforma=proforma,
        Fecha_de_la_factura=fecha,
        Referencia_de_pedido=ref,
        Importe=importe,
        Moneda=moneda_iso,
        Unidades=unidades,        
        confidence=confidence,
        source="rule",
        pais=envio_fields["Envio_Pais"],
        telefono=envio_fields["Envio_Telefono"],
        email=envio_fields["Envio_Email"],
    )
