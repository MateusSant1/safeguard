"""
Quando uma invasão é confirmada (pessoa dentro do perímetro), captura uma
sequência de frames e salva em disco -- essas imagens são o que vai
anexado na notificação do Telegram (implementada depois, em notifier.py).
"""
import time
from datetime import datetime
from pathlib import Path

import cv2

from server.config import EVENTS_DIR, FRAMES_PER_EVENT


class EventRecorder:
    def __init__(self, frames_per_event: int = FRAMES_PER_EVENT, interval_seconds: float = 0.4):
        """
        interval_seconds: pausa entre cada frame capturado dentro de um
        mesmo evento -- existe pra que as ~5 imagens mostrem a cena
        evoluindo ao longo de ~2 segundos, em vez de serem 5 cópias quase
        idênticas do mesmo instante.
        """
        self._frames_per_event = frames_per_event
        self._interval_seconds = interval_seconds

    def capture_event(self, camera) -> list[Path]:
        """
        Captura frames_per_event frames em sequência e salva em
        EVENTS_DIR/<timestamp>/frame_00.jpg, frame_01.jpg, ...

        Recebe o objeto `camera` (já aberto) em vez de abrir uma câmera
        própria -- assim usa o mesmo frame stream que o resto do
        pipeline, sem disputar o dispositivo com outra captura.

        Retorna a lista de caminhos das imagens salvas (pode vir mais
        curta que frames_per_event se algum frame falhar na leitura).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        event_dir = EVENTS_DIR / timestamp
        event_dir.mkdir(parents=True, exist_ok=True)

        caminhos: list[Path] = []
        for i in range(self._frames_per_event):
            frame = camera.read_frame()
            if frame is not None:
                caminho = event_dir / f"frame_{i:02d}.jpg"
                cv2.imwrite(str(caminho), frame)
                caminhos.append(caminho)

            is_last = i == self._frames_per_event - 1
            if not is_last:
                time.sleep(self._interval_seconds)

        return caminhos
