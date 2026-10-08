"""
Lista quais índices de câmera funcionam no seu computador. No Windows é
comum ter mais de um dispositivo de vídeo registrado (câmeras virtuais de
Zoom, Teams, OBS etc.), então nem sempre o índice 0 é a sua webcam física.

Uso:
    python server/list_cameras.py
"""
import cv2

MAX_INDEX_TO_TRY = 5


def main() -> None:
    encontrados = []

    for index in range(MAX_INDEX_TO_TRY + 1):
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            continue

        ok, frame = cap.read()
        if ok and frame is not None:
            height, width = frame.shape[:2]
            filename = f"camera_{index}.jpg"
            cv2.imwrite(filename, frame)
            print(f"[OK] Índice {index}: {width}x{height} -- frame salvo em '{filename}'")
            encontrados.append(index)
        else:
            print(f"[--] Índice {index}: abriu, mas não retornou frame")

        cap.release()

    print()
    if not encontrados:
        print(
            "Nenhuma câmera respondeu. Verifique se ela está conectada e "
            "se nenhum outro programa (Zoom, Teams, OBS...) está usando-a."
        )
    else:
        print(f"Índices que funcionaram: {encontrados}")
        print(
            "Abra os arquivos camera_<indice>.jpg gerados nesta pasta para "
            "ver qual imagem é a da sua webcam de verdade."
        )


if __name__ == "__main__":
    main()
