"""
Envia a notificação de invasão para o Telegram, usando a Bot API
diretamente via `requests` (sem wrapper -- este bot só envia, não recebe
comandos).

Cuidado: o token faz parte da URL da API. Por isso os erros daqui nunca
repassam a exceção original do `requests` (que inclui a URL com o token):
levantamos um RuntimeError só com o código HTTP e a descrição do Telegram.
"""
import json
import logging
from contextlib import ExitStack
from pathlib import Path

import requests

from server.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_ALBUM_SIZE = 10  # limite do sendMediaGroup
CAPTION_LIMIT = 1024  # limite de legenda do Telegram
TIMEOUT = (5, 30)  # (conexão, leitura) em segundos


def _call(method: str, data: dict, files: dict) -> None:
    url = API_URL.format(token=TELEGRAM_BOT_TOKEN, method=method)
    try:
        resp = requests.post(url, data=data, files=files, timeout=TIMEOUT)
    except requests.RequestException as e:
        # Só o tipo do erro: a mensagem do requests carrega a URL (com token).
        raise RuntimeError(f"Falha de rede ao chamar o Telegram ({type(e).__name__}).") from None

    try:
        body = resp.json()
    except ValueError:
        body = {}

    if resp.status_code != 200 or not body.get("ok"):
        descricao = body.get("description", "sem descrição")
        raise RuntimeError(f"Telegram recusou {method}: HTTP {resp.status_code} - {descricao}")


def send_alert(image_paths: list[Path], caption: str = "Invasão detectada!") -> None:
    """
    Envia a mensagem + imagens do evento para o chat configurado: uma foto
    solta se houver só uma, ou um álbum (sendMediaGroup, até 10) se houver
    mais -- a legenda aparece na primeira foto do álbum.

    Levanta exceção se TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não estiverem
    configurados, se não houver imagens ou se o Telegram recusar -- não
    falhar silenciosamente aqui, é melhor aparecer no log do servidor.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar definidos no .env."
        )

    paths = [Path(p) for p in image_paths][:MAX_ALBUM_SIZE]
    if not paths:
        raise ValueError("Nenhuma imagem para enviar.")

    caption = caption[:CAPTION_LIMIT]

    with ExitStack() as stack:
        if len(paths) == 1:
            files = {"photo": stack.enter_context(open(paths[0], "rb"))}
            _call("sendPhoto", {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files)
        else:
            media = []
            files = {}
            for i, path in enumerate(paths):
                nome = f"photo{i}"
                files[nome] = stack.enter_context(open(path, "rb"))
                item = {"type": "photo", "media": f"attach://{nome}"}
                if i == 0:
                    item["caption"] = caption
                media.append(item)
            _call(
                "sendMediaGroup",
                {"chat_id": TELEGRAM_CHAT_ID, "media": json.dumps(media)},
                files,
            )

    logger.info("Alerta enviado ao Telegram (%d imagem(ns)).", len(paths))
