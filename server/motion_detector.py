"""
Estágio 1 do pipeline: gatilho de movimento barato.

Roda continuamente sobre os frames da câmera (idealmente em baixa
resolução) e só avisa "tem movimento" quando a área de pixels alterados,
DENTRO da máscara do perímetro, ultrapassa um limiar. Não sabe nada sobre
pessoas/animais -- isso é trabalho do object_detector.py no estágio
seguinte, que só deve ser chamado quando detect() retornar True.

Detalhe importante de operação: o subtrator de fundo (MOG2) precisa de
alguns frames para "aprender" como é o fundo parado da cena. Nos
primeiros frames depois de start()/reset(), é normal e esperado que
detect() acuse movimento mesmo sem ninguém na cena -- use warm_up() para
consumir esses frames iniciais antes de começar a agir sobre o resultado.
"""
import cv2
import numpy as np


class MotionDetector:
    def __init__(
        self,
        threshold_area: int = 500,
        history: int = 500,
        var_threshold: float = 16.0,
    ):
        """
        threshold_area: área mínima (em pixels) de uma região alterada
            para contar como "movimento real" -- filtra ruído da câmera
            (pequenas variações de luz, compressão, etc.) que a subtração
            de fundo sozinha não elimina.
        history / var_threshold: repassados direto para o
            cv2.createBackgroundSubtractorMOG2 -- history é quantos frames
            ele usa pra formar o modelo de fundo; var_threshold controla a
            sensibilidade (menor = mais sensível a pequenas mudanças).
        """
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=var_threshold, detectShadows=False
        )
        self._threshold_area = threshold_area
        # Kernel usado para limpar ruído da máscara de movimento antes de
        # procurar contornos (remove pontinhos isolados de 1-2 pixels).
        self._clean_kernel = np.ones((3, 3), np.uint8)
        # Resultado da última chamada a detect(), para diagnóstico (o
        # pipeline desenha isso no vídeo): máscara de movimento já limpa e
        # restrita ao perímetro, e a área da maior região encontrada.
        self.last_mask: np.ndarray | None = None
        self.last_area: float = 0.0

    def warm_up(self, frames) -> None:
        """
        Alimenta o subtrator com frames iniciais sem verificar movimento,
        para ele aprender o fundo da cena antes de qualquer detecção real
        valer a pena. Chame isso com uns 20-30 frames ao iniciar o
        servidor (ou depois de qualquer mudança grande na cena).
        """
        for frame in frames:
            self._subtractor.apply(frame)

    def detect(self, frame: np.ndarray, perimeter_mask: np.ndarray | None = None) -> bool:
        """
        Retorna True se uma região de movimento com área >= threshold_area
        foi encontrada dentro da máscara do perímetro (ou no frame inteiro,
        se perimeter_mask for None).
        """
        fg_mask = self._subtractor.apply(frame)

        if perimeter_mask is not None:
            fg_mask = cv2.bitwise_and(fg_mask, perimeter_mask)

        # Remove ruído isolado antes de medir área -- sem isso, poeira de
        # compressão de vídeo já basta pra disparar falso positivo.
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._clean_kernel)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        maior_area = max((cv2.contourArea(c) for c in contours), default=0)

        self.last_mask = fg_mask
        self.last_area = float(maior_area)
        return maior_area >= self._threshold_area

    @property
    def threshold_area(self) -> int:
        return self._threshold_area
