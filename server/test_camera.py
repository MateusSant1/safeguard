"""
Script de sanidade do ambiente: confirma que o OpenCV consegue abrir a
câmera e capturar frames antes de qualquer lógica de visão computacional
entrar em cena. Rode isto primeiro, tanto no notebook quanto no Pi.

Uso:
    python server/test_camera.py
"""
import os
import sys
import time

import cv2

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))


def main() -> None:
    print(f"Tentando abrir a câmera de índice {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("ERRO: não foi possível abrir a câmera. Verifique:")
        print("  - Se a webcam está conectada (ls /dev/video* no Linux)")
        print("  - Se CAMERA_INDEX está correto (tente 0, 1, 2...)")
        sys.exit(1)

    ok, frame = cap.read()
    if not ok:
        print("ERRO: a câmera abriu, mas não retornou nenhum frame.")
        sys.exit(1)

    height, width = frame.shape[:2]
    print(f"OK! Frame capturado com sucesso: {width}x{height} pixels.")

    out_path = "test_frame.jpg"
    cv2.imwrite(out_path, frame)
    print(f"Frame salvo em '{out_path}' para conferência visual.")

    cap.release()


if __name__ == "__main__":
    main()
