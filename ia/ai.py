import logging

def generate_text(prompt):
    """
    Gera texto baseado no prompt fornecido.
    Para MVP, usa resposta mock simples.
    """
    logging.info(f"Gerando texto para prompt: {prompt}")
    return f"Resposta mock para: {prompt}"