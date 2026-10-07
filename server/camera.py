"""
Responsabilidade única: abrir a webcam e entregar frames.

Nenhum outro módulo deve chamar cv2.VideoCapture diretamente — tudo passa
por aqui, para que trocar de câmera (webcam USB -> câmera do Pi, por
exemplo) signifique mexer em um arquivo só.
"""
import logging

import cv2
import numpy as np

from server.config import CAMERA_INDEX

logger = logging.getLogger(__name__)


class Camera:
    def __init__(self, index: int = CAMERA_INDEX):
        self._index = index
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> None:
        """Abre a captura de vídeo. Levanta RuntimeError se falhar."""
        self._cap = cv2.VideoCapture(self._index)
        if not self._cap.isOpened():
            self._cap = None
            raise RuntimeError(
                f"Não foi possível abrir a câmera de índice {self._index}. "
                "Verifique se ela está conectada (ls /dev/video* no Linux) "
                "e se CAMERA_INDEX está correto."
            )
        logger.info("Câmera %s aberta com sucesso.", self._index)

    def read_frame(self) -> np.ndarray | None:
        """Retorna o frame mais recente (numpy array BGR) ou None se falhar."""
        if self._cap is None:
            raise RuntimeError("A câmera não foi iniciada. Chame start() primeiro.")

        ok, frame = self._cap.read()
        if not ok:
            logger.warning("Falha ao ler frame da câmera %s.", self._index)
            return None
        return frame

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
