
def generateBody(idioma: str, importe: float, moneda: str, numeroPedido: int, fechaFactura: str):
    """Genera el cuerpo del correo electrónico de solicitud de pago."""
    match idioma.lower():
        case "español" | "es":
            subject = f"Pendiente de pago proforma nº pedido {numeroPedido}"
            body = f"Estimado cliente,\n\nLe informamos de que, salvo error por nuestra parte, no hemos recibido el pago de la proforma por importe de {importe} {moneda} correspondiente al pedido número {numeroPedido} que le enviamos por correo el pasado {fechaFactura}.\n\nRogamos que proceda al pago de la misma para que podamos enviarle su pedido, a la mayor brevedad posible.\n\nSi necesita más información, no dude en contactar con nosotros.\nGracias de antemano.\n\nUn saludo."
        case "english" | "en":
            subject = f"Payment not received for order {numeroPedido}"
            body = f"Dear Customer,\n\nKindly, we would like to inform you that, unless we made any mistake, we have not received the payment of {importe} {moneda} corresponding to the order {numeroPedido} that we sent you on {fechaFactura}.\n\nWe kindly request you to proceed with this payment in order to release your expedition as soon as possible.\n\nIf you require any further information, please do not hesitate to contact us.\n\nThank you.\nBest regards,"
        case "français" | "fr":
            subject = f"Paiement non reçu pour la commande {numeroPedido}"
            body = f"Cher client,\n\nNous vous prions de bien vouloir effectuer le paiement de {importe} {moneda} pour la commande numéro {numeroPedido} datée du {fechaFactura}.\n\nMerci pour votre attention.\n\nCordialement,\nVotre entreprise"
        case "deutsch" | "de":
            subject = f"Zahlung nicht erhalten für die Bestellung {numeroPedido}"
            body = f"Sehr geehrter Kunde,\n\nWir bitten Sie um die Zahlung von {importe} {moneda} für die Bestellung Nummer {numeroPedido} vom {fechaFactura}.\n\nVielen Dank für Ihre Aufmerksamkeit.\n\nMit freundlichen Grüßen,\nIhr Unternehmen"
        case "italiano" | "it":
            subject = f"Pagamento non ricevuto per l'ordine {numeroPedido}"
            body = f"Caro cliente,\n\nLa preghiamo di effettuare il pagamento di {importe} {moneda} per l'ordine numero {numeroPedido} datato {fechaFactura}.\n\nGrazie per la sua attenzione.\n\nCordiali saluti,\nLa Sua Azienda"
        case "português" | "pt":
            subject = f"Pagamento não recebido para o pedido {numeroPedido}"
            body = f"Caro cliente,\n\nSolicitamos gentilmente o pagamento de {importe} {moneda} referente ao pedido número {numeroPedido} datado de {fechaFactura}.\n\nObrigado pela sua atenção.\n\nAtenciosamente,\nSua Empresa"
        case "rumano" | "ro":
            subject = f"Plată neprimita pentru comanda {numeroPedido}"
            body = f"Stimate client,\n\nVă rugăm să efectuați plata de {importe} {moneda} pentru comanda numărul {numeroPedido} datată {fechaFactura}.\n\nVă mulțumim pentru atenție.\n\nCu stimă,\nCompania Dumneavoastră"
        case _:
            subject = f"Payment not received for order {numeroPedido}"
            body = f"Dear Customer,\n\nKindly, we would like to inform you that, unless we made any mistake, we have not received the payment of {importe} {moneda} corresponding to the order {numeroPedido} that we sent you on {fechaFactura}.\n\nWe kindly request you to proceed with this payment in order to release your expedition as soon as possible.\n\nIf you require any further information, please do not hesitate to contact us.\n\nThank you.\nBest regards,"

    return body, subject