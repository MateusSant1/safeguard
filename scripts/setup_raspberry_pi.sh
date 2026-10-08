#!/usr/bin/env bash
#
# Safeguard — prepara o ambiente do projeto no Raspberry Pi 3.
#
# Rode como seu usuário normal (NÃO com sudo); o script pede a senha do sudo
# quando precisa instalar pacotes do sistema.
#
#   Dentro do repositório já clonado:   bash scripts/setup_raspberry_pi.sh
#   Fora dele (clona em ~/safeguard):   bash setup_raspberry_pi.sh
#
# Variáveis opcionais:
#   REPO_URL      repositório a clonar (padrão: MateusSant1/safeguard)
#   BRANCH        branch a clonar (padrão: main)
#   PROJECT_DIR   pasta do projeto (padrão: a raiz do repositório onde este
#                 script está, ou ~/safeguard)
#   SKIP_UPGRADE  =1 para pular o "apt full-upgrade" (mais rápido)
#
# O que ele faz:
#   1. mostra a versão do sistema
#   2. atualiza o sistema
#   3. instala git, curl, venv, OpenCV e NumPy pelo apt
#   4. clona ou atualiza o código
#   5. cria o .venv (enxergando o OpenCV do apt) e instala requirements-pi.txt
#   6. baixa o modelo MobileNet-SSD
#   7. cria o .env e confere o acesso à câmera
#   8. roda a verificação do ambiente
#
# Pode ser rodado de novo sem problema: ele pula o que já está pronto.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/MateusSant1/safeguard.git}"
BRANCH="${BRANCH:-main}"
MODEL_BASE="https://github.com/PINTO0309/MobileNet-SSD-RealSense/raw/refs/heads/master/caffemodel/MobileNetSSD"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

if [ "$(id -u)" -eq 0 ]; then
    fail "Não rode com sudo/root. Rode como seu usuário: bash $0"
fi

# Se o script está dentro do repositório (scripts/), usa a raiz dele.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${PROJECT_DIR:-}" ]; then
    if [ -d "$SCRIPT_DIR/../server" ]; then
        PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    else
        PROJECT_DIR="$HOME/safeguard"
    fi
fi

# ---------------------------------------------------------------------------
step "1/8 Sistema"
# shellcheck disable=SC1091
. /etc/os-release
echo "SO:          ${PRETTY_NAME:-desconhecido}"
echo "Arquitetura: $(uname -m) ($(getconf LONG_BIT) bits)"
echo "Python:      $(python3 --version 2>&1)"
echo "Projeto em:  $PROJECT_DIR"
case "${VERSION_CODENAME:-}" in
    bookworm|trixie) ;;
    *) warn "Script pensado para Raspberry Pi OS Bookworm ou Trixie; você está em '${VERSION_CODENAME:-?}'." ;;
esac

# ---------------------------------------------------------------------------
step "2/8 Atualizando o sistema"
sudo apt-get update
if [ "${SKIP_UPGRADE:-0}" = "1" ]; then
    echo "SKIP_UPGRADE=1: pulando o full-upgrade."
else
    sudo apt-get full-upgrade -y
fi

# ---------------------------------------------------------------------------
step "3/8 Pacotes do sistema (OpenCV e NumPy vêm daqui, já compilados para ARM)"
sudo apt-get install -y \
    git curl \
    python3-venv python3-pip \
    python3-opencv python3-numpy \
    v4l-utils

# ---------------------------------------------------------------------------
step "4/8 Código do projeto"
if [ -d "$PROJECT_DIR/.git" ]; then
    git -C "$PROJECT_DIR" pull --ff-only || warn "git pull falhou; seguindo com os arquivos que já estão na pasta."
elif [ -d "$PROJECT_DIR/server" ]; then
    echo "Usando a pasta existente (não é um clone git)."
else
    git clone -b "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"

if [ ! -s server/camera.py ] || [ ! -s server/object_detector.py ]; then
    fail "Os arquivos de server/ estão vazios ou faltando. Atualize o código (git checkout main && git pull) e rode este script de novo."
fi

# ---------------------------------------------------------------------------
step "5/8 Ambiente virtual e bibliotecas Python"
# --system-site-packages: o .venv enxerga o OpenCV e o NumPy instalados pelo apt.
if [ ! -d .venv ]; then
    python3 -m venv --system-site-packages .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip

# Se alguém instalou OpenCV ou NumPy pelo pip dentro do .venv, eles escondem as
# versões do apt (e o pip pode ter trazido o OpenCV 5, que não lê Caffe).
for pkg in opencv-python opencv-python-headless opencv-contrib-python numpy; do
    loc="$(pip show "$pkg" 2>/dev/null | sed -n 's/^Location: //p')"
    case "$loc" in
        */.venv/*)
            warn "Removendo $pkg instalado pelo pip dentro do .venv (o do apt é o que deve ser usado)."
            pip uninstall -y "$pkg"
            ;;
    esac
done

if [ -f requirements-pi.txt ]; then
    pip install -r requirements-pi.txt
else
    pip install "flask>=3.0,<4" "flask-socketio>=5.3,<6" "python-dotenv>=1.0" "requests>=2.31"
fi

# ---------------------------------------------------------------------------
step "6/8 Modelo de detecção (MobileNet-SSD)"
mkdir -p server/models server/data server/events

download() {
    # download <arquivo> <tamanho mínimo em bytes>
    local name="$1" min="$2" dest="server/models/$1"
    if [ -f "$dest" ] && [ "$(stat -c%s "$dest")" -ge "$min" ]; then
        echo "$name já existe ($(stat -c%s "$dest") bytes)."
        return
    fi
    echo "Baixando $name..."
    curl -fL --retry 3 -o "$dest" "$MODEL_BASE/$name"
    if [ "$(stat -c%s "$dest")" -lt "$min" ]; then
        fail "$name veio incompleto ($(stat -c%s "$dest") bytes). Apague o arquivo e rode de novo."
    fi
}
# Os dois arquivos precisam vir da MESMA fonte (senão: erro blobs.size() >= 2).
download MobileNetSSD_deploy.prototxt 10000
download MobileNetSSD_deploy.caffemodel 20000000

# ---------------------------------------------------------------------------
step "7/8 Configuração e câmera"
if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    echo ".env criado a partir de .env.example (preencha o Telegram quando for usar)."
fi

if [ -f server/data/perimeter.json ] && [ ! -s server/data/perimeter.json ]; then
    rm server/data/perimeter.json
    echo "server/data/perimeter.json estava vazio e foi removido (o sistema passa a vigiar a imagem inteira)."
fi

PRECISA_RELOGAR=0
if [[ " $(id -nG) " != *" video "* ]]; then
    sudo usermod -aG video "$USER"
    PRECISA_RELOGAR=1
    warn "Usuário $USER adicionado ao grupo 'video' (acesso à câmera). Saia e entre de novo no SSH."
fi

if ls /dev/video* >/dev/null 2>&1; then
    v4l2-ctl --list-devices || true
else
    warn "Nenhuma câmera em /dev/video*. Confira se a webcam está conectada (lsusb) e rode de novo."
fi

# ---------------------------------------------------------------------------
step "8/8 Verificação do ambiente"
if [ -f scripts/verificar_ambiente.py ]; then
    python scripts/verificar_ambiente.py
else
    warn "scripts/verificar_ambiente.py não encontrado; fazendo só a checagem mínima."
    python - <<'PY'
import sys, cv2
major = int(cv2.__version__.split(".")[0])
print("OpenCV", cv2.__version__)
if major >= 5 or not hasattr(cv2.dnn, "readNetFromCaffe"):
    sys.exit("ERRO: é preciso OpenCV 4.x com cv2.dnn.readNetFromCaffe")
PY
fi

cat <<EOF

Instalação concluída.

Próximos passos (a partir de $PROJECT_DIR):
  source .venv/bin/activate
  python server/list_cameras.py          # descobre o índice da webcam
  python -m server.test_telegram         # configura e testa o Telegram
  python -m server.app                   # inicia; abra http://<IP do Pi>:5000
O IP do Pi aparece com: hostname -I
EOF
if [ "$PRECISA_RELOGAR" = "1" ]; then
    echo "Lembre-se: saia e entre de novo no SSH antes de usar a câmera."
fi
