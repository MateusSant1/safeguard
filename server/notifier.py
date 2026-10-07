"""
Envia a notificação de invasão para o Telegram, usando a Bot API
diretamente via `requests` (sem wrapper -- este bot só envia, não recebe
comandos).
"""
from pathlib import Path

import requests

from server.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_alert(image_paths: list[Path], caption: str = "Invasão detectada!") -> None:
    """
    Envia a mensagem + imagens do evento para o chat configurado.
    Levanta exceção se TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não estiverem
    configurados -- não falhar silenciosamente aqui, é melhor aparecer
    no log do servidor.
    """
    # TODO:
    #   url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    #   para cada imagem (ou usar sendMediaGroup para mandar as ~5 juntas),
    #   requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
    #                 files={"photo": open(caminho, "rb")})
    raise NotImplementedError
