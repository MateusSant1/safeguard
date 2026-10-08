"""
Quando uma invasão é confirmada (pessoa dentro do perímetro), salva uma
sequência de frames em disco -- essas imagens são o que vai anexado na
notificação do Telegram (notifier.py).

Dois jeitos de usar:
  - start_event(): NÃO bloqueia. Salva o frame da detecção e devolve um
    PendingEvent, que recebe os frames seguintes do loop (offer) e salva um
    a cada interval_seconds. É o que o pipeline usa: o vídeo e a detecção
    continuam rodando enquanto o evento é gravado.
  - capture_event(): bloqueia lendo direto da câmera. Usado pelos scripts
    de teste (test_pipeline.py).
"""
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from server.config import EVENT_FRAME_INTERVAL_SECONDS, EVENTS_DIR, FRAMES_PER_EVENT


class PendingEvent:
    """Evento em gravação: acumula frames até completar frames_per_event."""

    def __init__(self, event_dir: Path, frames_per_event: int, interval_seconds: float):
        self.event_dir = event_dir
        self.paths: list[Path] = []
        self._frames_per_event = frames_per_event
        self._interval = interval_seconds
        self._next_due = 0.0

    @property
    def event_id(self) -> str:
        return self.event_dir.name

    @property
    def done(self) -> bool:
        return len(self.paths) >= self._frames_per_event

    def offer(self, frame: np.ndarray, now: float | None = None) -> bool:
        """
        Oferece um frame do loop. Salva se já passou o intervalo desde o
        anterior; ignora caso contrário. Retorna True quando o evento fica
        completo.
        """
        now = time.monotonic() if now is None else now
        if not self.done and now >= self._next_due:
            caminho = self.event_dir / f"frame_{len(self.paths):02d}.jpg"
            if cv2.imwrite(str(caminho), frame):
                self.paths.append(caminho)
                self._next_due = now + self._interval
        return self.done


class EventRecorder:
    def __init__(
        self,
        frames_per_event: int = FRAMES_PER_EVENT,
        interval_seconds: float = EVENT_FRAME_INTERVAL_SECONDS,
    ):
        """
        interval_seconds: pausa entre cada frame capturado dentro de um
        mesmo evento -- existe pra que as imagens mostrem a cena evoluindo
        (com 5 frames e 1 s, cerca de 4 s de cena), em vez de serem cópias
        quase idênticas do mesmo instante.
        """
        self._frames_per_event = frames_per_event
        self._interval_seconds = interval_seconds

    def _new_event_dir(self) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        event_dir = EVENTS_DIR / timestamp
        event_dir.mkdir(parents=True, exist_ok=True)
        return event_dir

    def start_event(self, first_frame: np.ndarray) -> PendingEvent:
        """
        Abre um evento novo e já salva first_frame (o frame da detecção,
        garante que a pessoa aparece) como frame_00. Os demais vêm de
        PendingEvent.offer().
        """
        evento = PendingEvent(
            self._new_event_dir(), self._frames_per_event, self._interval_seconds
        )
        evento.offer(first_frame)
        return evento

    def capture_event(self, camera, first_frame: np.ndarray | None = None) -> list[Path]:
        """
        Versão bloqueante: captura frames_per_event frames em sequência,
        lendo da câmera (já aberta), e salva em
        EVENTS_DIR/<timestamp>/frame_00.jpg, frame_01.jpg, ...

        first_frame: se vier, é salvo como frame_00 e só os demais são
        lidos da câmera.

        Retorna a lista de caminhos das imagens salvas (pode vir mais
        curta que frames_per_event se algum frame falhar na leitura).
        """
        event_dir = self._new_event_dir()

        caminhos: list[Path] = []
        for i in range(self._frames_per_event):
            if i == 0 and first_frame is not None:
                frame = first_frame
            else:
                if i > 0:
                    time.sleep(self._interval_seconds)
                frame = camera.read_frame()

            if frame is not None:
                caminho = event_dir / f"frame_{i:02d}.jpg"
                cv2.imwrite(str(caminho), frame)
                caminhos.append(caminho)

        return caminhos
