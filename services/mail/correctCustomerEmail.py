from typing import Optional
from models.data import correctEmailOutput
from services.database.cobroProforma import find_client_email, DatabaseUnavailable
from services.pdfReading.pdfDataExtraction import is_valid_email

def _output(email_pdf: str, email_aplicado: str, email_bd: str, es_corregido: bool,
            motivo: Optional[str], es_email_pdf_valido: bool) -> correctEmailOutput:
    return correctEmailOutput(
        email_aplicado=email_aplicado,
        email_bd=email_bd,
        es_corregido=es_corregido,
        motivo=motivo,
        es_email_pdf_valido=es_email_pdf_valido,
        email_cliente=email_aplicado,
        es_email_corregido=1 if es_corregido else 0,
        # Solo se guarda si es_email_corregido = 1
        email_pdf_cliente=email_pdf if es_corregido else "",
    )

def correctCustomerEmail(num_pedido: int, email_pdf: str) -> correctEmailOutput:
    """
    Corrige el email del PDF con el de la BD de clientes (v_consulta_email) por nº de pedido.
    Si el email del PDF es válido o viene vacío no se consulta la BD y se aplica tal cual.
    motivo: match | replaced | bd_sin_email | bd_no_disponible (None si no se consulta la BD).
    """
    email_pdf = (email_pdf or "").strip()

    if not email_pdf or is_valid_email(email_pdf):
        return _output(email_pdf, email_pdf, "", False, None, bool(email_pdf))

    try:
        email_bd = (find_client_email(num_pedido) or "").strip()
    except DatabaseUnavailable:
        motivo, email_bd = "bd_no_disponible", ""
    else:
        if not email_bd:
            motivo = "bd_sin_email"
        elif email_bd.lower() == email_pdf.lower():
            motivo = "match"
        else:
            motivo = "replaced"

    print(f"CORREGIR EMAIL: pedido={num_pedido} pdf='{email_pdf}' -> BD: '{email_bd}' ({motivo})")

    email_aplicado = email_bd if motivo in ("match", "replaced") else ""
    return _output(email_pdf, email_aplicado, email_bd, motivo == "replaced", motivo, False)
