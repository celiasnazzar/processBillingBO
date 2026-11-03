from models.data import correctEmailOutput
from services.database.cobroProforma import find_client_email, DatabaseUnavailable
from services.pdfReading.pdfDataExtraction import is_valid_email

def correctCustomerEmail(num_pedido: int, email_pdf: str) -> correctEmailOutput:
    """
    Corrige el email del PDF con el de la BD de clientes (v_consulta_email) por nº de pedido.
    Si el email del PDF es válido o viene vacío no se consulta la BD y se aplica tal cual.
    motivo: match | replaced | bd_sin_email | bd_no_disponible (None si no se consulta la BD).
    """
    email_pdf = (email_pdf or "").strip()

    if not email_pdf or is_valid_email(email_pdf):
        return correctEmailOutput(
            email_aplicado=email_pdf,
            email_bd=None,
            es_corregido=False,
            motivo=None,
            es_email_pdf_valido=bool(email_pdf),
        )

    try:
        email_bd = find_client_email(num_pedido)
    except DatabaseUnavailable:
        motivo, email_bd = "bd_no_disponible", None
    else:
        if not email_bd:
            motivo = "bd_sin_email"
        elif email_bd.strip().lower() == email_pdf.lower():
            motivo = "match"
        else:
            motivo = "replaced"

    print(f"CORREGIR EMAIL: pedido={num_pedido} pdf='{email_pdf}' -> BD: {email_bd} ({motivo})")

    return correctEmailOutput(
        email_aplicado=email_bd.strip() if motivo in ("match", "replaced") else "",
        email_bd=email_bd,
        es_corregido=motivo == "replaced",
        motivo=motivo,
        es_email_pdf_valido=False,
    )
