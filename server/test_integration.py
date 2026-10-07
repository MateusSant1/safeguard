"""
Teste de integração manual: usa a classe Camera (camera.py) junto com as
funções de perimeter.py, captura um frame REAL da sua webcam, desenha um
perímetro de exemplo por cima e salva a imagem para conferência visual.

Isso confirma, tudo de uma vez, que:
  - a classe Camera abre a sua webcam de verdade e entrega frames;
  - a conversão de coordenadas normalizadas -> pixels (denormalize) bate
    certinho com as dimensões reais do frame da sua câmera;
  - point_inside_perimeter reconhece corretamente um ponto de teste
    dentro e outro fora do perímetro desenhado.

Uso:
    python server/test_integration.py
"""
import cv2

from server.camera import Camera
from server.perimeter import denormalize, point_inside_perimeter

# Perímetro de exemplo: um retângulo cobrindo a região central do frame.
# Em produção, isso viria do server/data/perimeter.json (desenhado pelo
# usuário no navegador) via perimeter.load_perimeter().
PERIMETRO_EXEMPLO = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]


def main() -> None:
    with Camera() as cam:
        largura, altura = cam.get_dimensions()
        print(f"Câmera aberta: {largura}x{altura}")

        frame = cam.read_frame()
        if frame is None:
            print("ERRO: não foi possível capturar um frame.")
            return

    polygon_px = denormalize(PERIMETRO_EXEMPLO, largura, altura)

    # Desenha o perímetro por cima do frame, em verde.
    frame_com_perimetro = frame.copy()
    cv2.polylines(
        frame_com_perimetro, [polygon_px], isClosed=True, color=(0, 255, 0), thickness=3
    )

    # Testa dois pontos: o centro do frame (deve estar DENTRO do
    # retângulo de exemplo) e o canto superior esquerdo (deve estar FORA).
    centro = (largura // 2, altura // 2)
    canto = (5, 5)

    dentro_centro = point_inside_perimeter(centro, polygon_px)
    dentro_canto = point_inside_perimeter(canto, polygon_px)

    cor_centro = (0, 255, 0) if dentro_centro else (0, 0, 255)
    cor_canto = (0, 255, 0) if dentro_canto else (0, 0, 255)
    cv2.circle(frame_com_perimetro, centro, 8, cor_centro, -1)
    cv2.circle(frame_com_perimetro, canto, 8, cor_canto, -1)

    saida = "test_perimetro.jpg"
    cv2.imwrite(saida, frame_com_perimetro)

    print(f"Centro do frame {centro} está dentro do perímetro? {dentro_centro} (esperado: True)")
    print(f"Canto do frame {canto} está dentro do perímetro? {dentro_canto} (esperado: False)")
    print(f"Imagem salva em '{saida}' -- abra e confira visualmente o retângulo verde.")


if __name__ == "__main__":
    main()
