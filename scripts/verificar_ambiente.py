"""
Confere se o ambiente está pronto para rodar o Safeguard.

Funciona no computador de desenvolvimento e no Raspberry Pi. Rode a partir da
raiz do projeto, com o .venv ativado:

    python scripts/verificar_ambiente.py

Verifica:
  1. versão do Python e das bibliotecas;
  2. OpenCV 4.x com suporte a modelos Caffe (o OpenCV 5 removeu esse suporte);
  3. arquivos do modelo MobileNet-SSD presentes e com o tamanho esperado;
  4. uma inferência de teste com o modelo (o "forward"), que é o que acusa
     prototxt e caffemodel incompatíveis;
  5. arquivo .env presente.

Termina com código de saída 0 se estiver tudo certo e 1 se houver erro.
"""
import importlib
import importlib.metadata
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELS = RAIZ / "server" / "models"
PROTOTXT = MODELS / "MobileNetSSD_deploy.prototxt"
CAFFEMODEL = MODELS / "MobileNetSSD_deploy.caffemodel"
CAFFEMODEL_MIN_BYTES = 20_000_000  # o arquivo correto tem ~22 MB

erros: list[str] = []
avisos: list[str] = []


def ok(msg: str) -> None:
    print(f"  [ok]    {msg}")


def aviso(msg: str) -> None:
    avisos.append(msg)
    print(f"  [aviso] {msg}")


def erro(msg: str) -> None:
    erros.append(msg)
    print(f"  [ERRO]  {msg}")


print(f"Python {sys.version.split()[0]} em {sys.executable}")
if sys.prefix == sys.base_prefix:
    aviso("o ambiente virtual (.venv) não parece estar ativado")

print("\nBibliotecas")
try:
    import cv2
    import numpy
except ImportError as e:
    erro(f"não foi possível importar OpenCV/NumPy: {e}")
    cv2 = None
else:
    ok(f"NumPy {numpy.__version__}")
    major = int(cv2.__version__.split(".")[0])
    if major >= 5:
        erro(
            f"OpenCV {cv2.__version__}: a versão 5 não lê modelos Caffe. "
            "Computador: pip install \"opencv-python>=4.9,<5\". "
            "Raspberry Pi: pip uninstall opencv-python opencv-python-headless "
            "(o OpenCV certo vem do apt)."
        )
    elif not hasattr(cv2.dnn, "readNetFromCaffe"):
        erro(f"OpenCV {cv2.__version__} sem cv2.dnn.readNetFromCaffe")
    else:
        ok(f"OpenCV {cv2.__version__} (com suporte a Caffe), carregado de {Path(cv2.__file__).parent}")

for modulo, nome in [
    ("flask", "Flask"),
    ("flask_socketio", "Flask-SocketIO"),
    ("dotenv", "python-dotenv"),
    ("requests", "Requests"),
]:
    try:
        importlib.import_module(modulo)
        try:
            versao = importlib.metadata.version(nome)
        except importlib.metadata.PackageNotFoundError:
            versao = ""
        ok(f"{nome} {versao}".rstrip())
    except ImportError:
        if modulo == "dotenv":
            erro(f"{nome} não instalado (config.py precisa dele)")
        else:
            aviso(f"{nome} não instalado (ainda não é usado pelo código atual)")

print("\nModelo MobileNet-SSD")
if not PROTOTXT.exists():
    erro(f"faltando {PROTOTXT.relative_to(RAIZ)}")
else:
    ok(f"{PROTOTXT.name} ({PROTOTXT.stat().st_size:,} bytes)")
if not CAFFEMODEL.exists():
    erro(f"faltando {CAFFEMODEL.relative_to(RAIZ)}")
elif CAFFEMODEL.stat().st_size < CAFFEMODEL_MIN_BYTES:
    erro(
        f"{CAFFEMODEL.name} com só {CAFFEMODEL.stat().st_size:,} bytes "
        "(download incompleto; o correto tem ~22 MB)"
    )
else:
    ok(f"{CAFFEMODEL.name} ({CAFFEMODEL.stat().st_size / 1e6:.1f} MB)")

if cv2 is not None and not erros:
    try:
        net = cv2.dnn.readNetFromCaffe(str(PROTOTXT), str(CAFFEMODEL))
        blob = cv2.dnn.blobFromImage(
            numpy.zeros((300, 300, 3), dtype="uint8"), 0.007843, (300, 300), 127.5
        )
        net.setInput(blob)
        saida = net.forward()
        ok(f"inferência de teste ok, saída com formato {tuple(saida.shape)}")
    except cv2.error as e:
        erro(
            "a inferência de teste falhou. Se o erro fala em blobs.size(), o "
            "prototxt e o caffemodel vieram de fontes diferentes: baixe os dois "
            f"de novo da mesma fonte. Detalhe: {str(e).strip().splitlines()[-1]}"
        )

print("\nConfiguração")
if (RAIZ / ".env").exists():
    ok(".env presente")
else:
    aviso(".env não existe (copie .env.example para .env)")

perimetro = RAIZ / "server" / "data" / "perimeter.json"
if perimetro.exists() and perimetro.stat().st_size == 0:
    aviso("server/data/perimeter.json está vazio: apague-o para vigiar a imagem inteira")

print()
if erros:
    print(f"{len(erros)} erro(s) encontrado(s). Corrija e rode de novo.")
    sys.exit(1)
print(f"Ambiente pronto ({len(avisos)} aviso(s)).")
