import re
from typing import List, Optional
from models.data import correctEmailOutput
from services.database.cobroProforma import find_client_email, DatabaseUnavailable
from services.pdfReading.pdfDataExtraction import is_valid_email

# Motivos con los que no hay un email utilizable: el cobro no puede recibir recordatorios
MOTIVOS_SIN_EMAIL = ("bd_sin_email", "bd_no_disponible")

def split_emails(value: str) -> List[str]:
    """Separa por ';' y ',', en minúsculas y sin espacios. Descarta los vacíos."""
    return [e for e in (re.sub(r"\s+", "", p).lower() for p in re.split(r"[;,]", value or "")) if e]

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
        # Solo se informa si es_email_corregido = 1; null si el PDF no traía email
        email_pdf_cliente=(email_pdf or None) if es_corregido else None,
    )

def correctCustomerEmail(num_pedido: Optional[int], email_pdf: str) -> correctEmailOutput:
    """
    Decide el email del cliente a partir del del PDF y, si hace falta, del de la BD de clientes
    (v_consulta_email, por nº de pedido).

    - Email del PDF válido: se aplica tal cual, sin consultar la BD (motivo None).
    - Email del PDF no válido (p. ej. cortado por la plantilla) o vacío: se consulta la BD.
        match            el del PDF está entre los de la BD          -> se aplica el de la BD, sin corrección
        replaced         el del PDF no está entre los de la BD,      -> se aplica el de la BD, es_corregido = 1
                         o el PDF no trae email y la BD sí              (email_pdf_cliente = null si el PDF no traía)
        bd_sin_email     la BD no tiene ningún email válido          -> email vacío: incidencia invalid_email
        bd_no_disponible sin configuración, error de BD o sin pedido -> email vacío: incidencia invalid_email
    """
    email_pdf = (email_pdf or "").strip()

    if email_pdf and is_valid_email(email_pdf):
        return _output(email_pdf, email_pdf, "", False, None, True)

    email_bd = ""
    if num_pedido is None:
        motivo = "bd_no_disponible"
    else:
        try:
            email_bd = (find_client_email(num_pedido) or "").strip()
        except DatabaseUnavailable:
            motivo = "bd_no_disponible"
        else:
            # Solo cuentan los emails de la BD con sintaxis válida
            emails_bd = [e for e in split_emails(email_bd) if is_valid_email(e)]
            if not emails_bd:
                motivo = "bd_sin_email"
            elif any(e in emails_bd for e in split_emails(email_pdf)):
                motivo = "match"
            else:
                motivo = "replaced"
            if emails_bd:
                email_bd = ";".join(emails_bd)

    print(f"CORREGIR EMAIL: pedido={num_pedido} pdf='{email_pdf}' -> BD: '{email_bd}' ({motivo})")

    email_aplicado = "" if motivo in MOTIVOS_SIN_EMAIL else email_bd
    return _output(email_pdf, email_aplicado, email_bd, motivo == "replaced", motivo, False)
