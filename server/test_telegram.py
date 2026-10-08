"""
Teste manual do Telegram, SEM câmera e sem modelo.

    python -m server.test_telegram

- Sem TELEGRAM_BOT_TOKEN no .env: explica como criar o bot.
- Com token mas sem TELEGRAM_CHAT_ID: lista os chats que mandaram mensagem
  ao bot, para você copiar o id certo para o .env.
- Com os dois: envia as imagens do evento mais recente de server/events/
  (ou uma imagem gerada, se ainda não houver evento).

O token nunca é impresso.
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from server.config import EVENTS_DIR, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from server.notifier import find_chats, send_alert


def latest_event_images() -> list[Path]:
    if not EVENTS_DIR.exists():
        return []
    pastas = sorted((d for d in EVENTS_DIR.iterdir() if d.is_dir()), reverse=True)
    for pasta in pastas:
        imagens = sorted(pasta.glob("frame_*.jpg"))
        if imagens:
            return imagens
    return []


def generated_image() -> Path:
    img = np.full((240, 320, 3), 40, np.uint8)
    cv2.putText(img, "Safeguard - teste", (30, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    caminho = Path(tempfile.gettempdir()) / "safeguard_teste.jpg"
    cv2.imwrite(str(caminho), img)
    return caminho


def main() -> int:
    if not TELEGRAM_BOT_TOKEN:
        print(
            "TELEGRAM_BOT_TOKEN vazio no .env.\n"
            "  1. No Telegram, abra @BotFather e envie /newbot.\n"
            "  2. Copie o token que ele devolver para TELEGRAM_BOT_TOKEN no .env.\n"
            "  3. Mande qualquer mensagem para o seu bot e rode este script de novo."
        )
        return 1

    if not TELEGRAM_CHAT_ID:
        chats = find_chats()
        if not chats:
            print(
                "Token OK, mas nenhum chat encontrado.\n"
                "Mande uma mensagem (ex.: 'oi') para o seu bot no Telegram e rode de novo."
            )
            return 1
        print("Token OK. Chats que falaram com o bot:")
        for c in chats:
            print(f"  TELEGRAM_CHAT_ID={c['id']}   ({c['tipo']}: {c['nome']})")
        print("Copie a linha do seu chat para o .env e rode este script de novo.")
        return 1

    imagens = latest_event_images()
    if imagens:
        print(f"Enviando {len(imagens)} imagem(ns) do evento {imagens[0].parent.name}...")
    else:
        print("Nenhum evento salvo ainda; enviando uma imagem de teste...")
        imagens = [generated_image()]

    send_alert(imagens, "Teste do Safeguard: se você está vendo isto, o Telegram está OK.")
    print("Enviado! Confira o Telegram.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
