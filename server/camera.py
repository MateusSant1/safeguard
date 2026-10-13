"""
Responsabilidade única: abrir a webcam e entregar frames.

Nenhum outro módulo deve chamar cv2.VideoCapture diretamente — tudo passa
por aqui, para que trocar de câmera (webcam USB -> câmera do Pi, por
exemplo) signifique mexer em um arquivo só.
"""
import logging
import sys
import time

import cv2
import numpy as np

from server.config import CAMERA_FOURCC, CAMERA_HEIGHT, CAMERA_INDEX, CAMERA_WIDTH

logger = logging.getLogger(__name__)

# Leituras falhas seguidas antes de fechar e reabrir o dispositivo (ex.: a
# webcam caiu e voltou no USB, o que acontece com fonte fraca no Pi).
FAILURES_BEFORE_REOPEN = 10


def open_capture(index: int) -> cv2.VideoCapture:
    """
    Abre o dispositivo já configurado. No Linux (Raspberry Pi) força o backend
    V4L2: o OpenCV do apt tenta o GStreamer primeiro, e ele falha com várias
    webcams ("cannot capture in the specified format"). Em outros sistemas
    mantém o backend padrão.

    Também é usada pelo list_cameras.py -- por isso fica fora da classe.
    """
    if sys.platform.startswith("linux"):
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(index)

    if cap.isOpened():
        # A ordem importa no V4L2: formato primeiro, depois resolução.
        if CAMERA_FOURCC:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*CAMERA_FOURCC[:4].ljust(4)))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        # Buffer de 1 frame: no Pi a detecção é lenta, e sem isso o pipeline
        # processaria imagens de alguns segundos atrás.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class Camera:
    def __init__(self, index: int = CAMERA_INDEX):
        self._index = index
        self._cap: cv2.VideoCapture | None = None
        self._failures = 0

    def start(self) -> None:
        """Abre a captura de vídeo. Levanta RuntimeError se falhar."""
        self._cap = open_capture(self._index)
        if not self._cap.isOpened():
            self._cap = None
            dica = (
                "Rode 'v4l2-ctl --list-devices' para achar a webcam, confira se o "
                "usuário está no grupo video ('groups') e ajuste CAMERA_INDEX no .env."
                if sys.platform.startswith("linux")
                else "Verifique se ela está conectada, se outro programa a está usando "
                "e se CAMERA_INDEX está correto."
            )
            raise RuntimeError(f"Não foi possível abrir a câmera de índice {self._index}. {dica}")

        largura, altura = self.get_dimensions()
        logger.info("Câmera %s aberta: %dx%d.", self._index, largura, altura)

    def read_frame(self) -> np.ndarray | None:
        """Retorna o frame mais recente (numpy array BGR) ou None se falhar."""
        if self._cap is None:
            raise RuntimeError("A câmera não foi iniciada. Chame start() primeiro.")

        try:
            ok, frame = self._cap.read()
        except cv2.error as e:
            # Quadro MJPEG vazio/corrompido: o OpenCV lança erro no imdecode
            # em vez de devolver ok=False. Tratamos como uma leitura falha.
            ok, frame = False, None
            if self._failures == 0:
                logger.warning(
                    "Quadro corrompido da câmera %s (%s).",
                    self._index, str(e).strip().splitlines()[-1],
                )

        if not ok or frame is None:
            if self._failures == 0:
                logger.warning("Falha ao ler frame da câmera %s.", self._index)
            self._failures += 1
            if self._failures % FAILURES_BEFORE_REOPEN == 0:
                self._reopen()
            return None

        if self._failures:
            logger.info("Câmera %s voltou após %d leitura(s) falha(s).", self._index, self._failures)
            self._failures = 0
        return frame

    def _reopen(self) -> None:
        logger.warning(
            "Câmera %s: %d falhas seguidas, reabrindo o dispositivo...",
            self._index, self._failures,
        )
        if self._cap is not None:
            self._cap.release()
        time.sleep(1.0)  # dá tempo de o USB reenumerar a webcam
        self._cap = open_capture(self._index)
        if not self._cap.isOpened():
            logger.error("Câmera %s não reabriu; nova tentativa em breve.", self._index)

    def get_dimensions(self) -> tuple[int, int]:
        """Retorna (largura, altura) reportadas pela câmera."""
        if self._cap is None:
            raise RuntimeError("A câmera não foi iniciada. Chame start() primeiro.")

        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height

    def stop(self) -> None:
        """Libera a câmera. Seguro chamar mesmo se ela nunca foi aberta."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Câmera %s liberada.", self._index)

    # Permite usar "with Camera() as cam:" para garantir que stop() é
    # chamado mesmo se der exceção no meio do uso.
    def __enter__(self) -> "Camera":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
