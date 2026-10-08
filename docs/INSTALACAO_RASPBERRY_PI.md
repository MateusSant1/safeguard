# Safeguard — Instalação no Raspberry Pi 3

Este guia prepara o Raspberry Pi 3 para rodar o Safeguard. Há duas formas de fazer a instalação: com o script automático (seção 2) ou comando a comando (seção 3). As duas fazem exatamente a mesma coisa.

**Pré-requisitos:** Raspberry Pi 3 com Raspberry Pi OS (Bookworm ou Trixie, 32 ou 64 bits) já instalado, conectado à internet e com SSH ativo; webcam USB conectada ao Pi.

**Como as bibliotecas são instaladas no Pi:** o OpenCV e o NumPy vêm do `apt` (`python3-opencv` e `python3-numpy`), e não do `pip`. Isso tem três motivos:

- os pacotes do `apt` já vêm compilados para o processador ARM do Pi, inclusive no sistema de 32 bits, que não tem pacotes oficiais do OpenCV no `pip`;
- compilar o OpenCV no Pi 3 levaria horas;
- o `apt` entrega OpenCV 4.x (4.6 no Bookworm, 4.10 no Trixie), enquanto o `pip` pode trazer o OpenCV 5, que não lê o modelo do projeto.

O ambiente virtual (`.venv`) é criado com `--system-site-packages` para enxergar esses dois pacotes. O `pip` instala só as bibliotecas em Python puro, listadas em `requirements-pi.txt`.

> **Não rode `pip install -r requirements.txt` no Pi.** Esse arquivo é do computador de desenvolvimento e instalaria um OpenCV do `pip` por cima do OpenCV do `apt`.

---

## 0. Onde está o código

O código está na branch **`main`** do repositório:

```bash
git clone https://github.com/MateusSant1/safeguard.git
```

O `.gitignore` impede o envio da `.venv`, do modelo (~22 MB), das imagens de teste e do `.env`. Ele também ignora o `CLAUDE.md`, como o grupo tinha decidido; se quiserem que todos recebam esse arquivo pelo Git, apaguem essa linha do `.gitignore`.

Para enviar mudanças feitas no Windows:

```powershell
git status          # a .venv/ e server/models/ não podem aparecer
git add .
git commit -m "Descreva a mudança"
git push
```

---

## 1. Entrar no Raspberry Pi

No PowerShell do Windows (troque `usuario` pelo usuário criado no Pi):

```powershell
ssh usuario@raspberrypi.local
```

Se `raspberrypi.local` não responder, use o IP do Pi. Ele aparece com `hostname -I` no próprio Pi ou na lista de dispositivos do roteador.

Já dentro do Pi, confira o sistema e a câmera:

```bash
cat /etc/os-release | grep PRETTY_NAME    # versão do Raspberry Pi OS
uname -m                                  # aarch64 = 64 bits, armv7l = 32 bits
lsusb                                     # a webcam deve aparecer na lista
ls /dev/video*                            # /dev/video0 = câmera reconhecida
vcgencmd get_throttled                    # 0x0 = alimentação e temperatura ok
```

Se `vcgencmd get_throttled` mostrar algo diferente de `0x0`, a fonte é fraca ou o Pi está esquentando demais. Use uma fonte de 5 V / 2,5 A e, de preferência, um dissipador.

---

## 2. Instalação automática (recomendada)

```bash
cd ~
git clone https://github.com/MateusSant1/safeguard.git
cd safeguard
bash scripts/setup_raspberry_pi.sh
```

Rode como seu usuário normal, **sem `sudo`**: o script pede a senha quando precisa. A primeira execução pode levar de 10 a 30 minutos, quase tudo no `apt full-upgrade`. Para pular essa atualização em execuções seguintes:

```bash
SKIP_UPGRADE=1 bash scripts/setup_raspberry_pi.sh
```

O script pode ser rodado de novo sem problema: ele pula o que já estiver pronto. Ao final, ele roda `scripts/verificar_ambiente.py`, que deve terminar com **"Ambiente pronto"**.

Se o script disser que seu usuário foi adicionado ao grupo `video`, saia do SSH (`exit`) e entre de novo antes de usar a câmera.

---

## 3. Instalação manual (comando a comando)

São os mesmos passos do script, para quem preferir entender ou depurar cada etapa.

### 3.1 Atualizar o sistema

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Espere o Pi reiniciar e entre de novo pelo SSH.

### 3.2 Pacotes do sistema

```bash
sudo apt install -y git curl python3-venv python3-pip python3-opencv python3-numpy v4l-utils
```

| Pacote | Para quê |
|---|---|
| `git` | baixar e atualizar o código |
| `curl` | baixar o modelo de detecção |
| `python3-venv`, `python3-pip` | ambiente virtual e instalador de bibliotecas Python |
| `python3-opencv` | OpenCV 4.x já compilado para ARM |
| `python3-numpy` | NumPy compatível com esse OpenCV |
| `v4l-utils` | comando `v4l2-ctl`, para listar e diagnosticar a webcam |

Confira a versão do OpenCV (tem que começar com 4) e o suporte ao formato do modelo:

```bash
python3 -c "import cv2; print(cv2.__version__, hasattr(cv2.dnn, 'readNetFromCaffe'))"
```

A saída esperada é algo como `4.10.0 True`.

### 3.3 Código do projeto

```bash
cd ~
git clone https://github.com/MateusSant1/safeguard.git
cd safeguard
```

### 3.4 Ambiente virtual e bibliotecas Python

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-pi.txt
```

O `requirements-pi.txt` instala `flask`, `flask-socketio`, `python-dotenv` e `requests`. O `(.venv)` no começo da linha do terminal indica que o ambiente virtual está ativo. Ele precisa ser ativado (`source .venv/bin/activate`) toda vez que você abrir um novo terminal.

### 3.5 Modelo de detecção (MobileNet-SSD)

Os dois arquivos precisam vir da **mesma fonte**. Arquivos de fontes diferentes causam o erro `blobs.size() >= 2`.

```bash
mkdir -p server/models server/data server/events
BASE="https://github.com/PINTO0309/MobileNet-SSD-RealSense/raw/refs/heads/master/caffemodel/MobileNetSSD"
curl -fL -o server/models/MobileNetSSD_deploy.prototxt   "$BASE/MobileNetSSD_deploy.prototxt"
curl -fL -o server/models/MobileNetSSD_deploy.caffemodel "$BASE/MobileNetSSD_deploy.caffemodel"
ls -lh server/models
```

O `.caffemodel` deve ter cerca de 22 MB.

### 3.6 Configuração

```bash
cp .env.example .env
nano .env        # CAMERA_INDEX e, quando forem usar, o token e o chat do Telegram
```

No `nano`, salve com `Ctrl+O` e saia com `Ctrl+X`.

Se existir um `server/data/perimeter.json` vazio, apague-o. Sem esse arquivo, o sistema vigia a imagem inteira.

```bash
[ -s server/data/perimeter.json ] || rm -f server/data/perimeter.json
```

### 3.7 Acesso à câmera

O usuário precisa estar no grupo `video`:

```bash
groups                               # "video" deve aparecer na lista
sudo usermod -aG video $USER         # só se não aparecer; depois saia e entre no SSH
v4l2-ctl --list-devices              # lista as câmeras e seus /dev/videoN
```

Muitas webcams USB criam dois dispositivos (`/dev/video0` e `/dev/video1`); normalmente a imagem está no de número menor.

### 3.8 Verificação

```bash
python scripts/verificar_ambiente.py
```

A verificação confere o OpenCV, os arquivos do modelo, uma inferência de teste com o modelo, as bibliotecas e o `.env`. Ela deve terminar com **"Ambiente pronto"**.

---

## 4. Testar no Pi

Sempre a partir da pasta do projeto, com o ambiente ativo:

```bash
cd ~/safeguard
source .venv/bin/activate
python server/list_cameras.py          # descobre o índice da webcam e salva camera_N.jpg
python -m server.test_integration      # câmera + perímetro; salva test_perimetro.jpg
```

Para ver as imagens geradas, copie-as para o Windows. No **PowerShell do Windows**:

```powershell
scp usuario@raspberrypi.local:~/safeguard/test_perimetro.jpg .
```

Os scripts `test_motion`, `test_object` e `test_pipeline` abrem uma janela com o vídeo (`cv2.imshow`). Pelo SSH não há tela para essa janela, e eles falham com um erro do tipo "cannot connect to X server" ou "could not connect to display". Esses três só rodam com monitor e teclado ligados ao Pi. Pelo SSH, teste o sistema completo pela interface web:

```bash
python -m server.test_telegram         # configura e testa o Telegram (sem câmera)
python -m server.app                   # inicia o sistema
hostname -I                            # IP do Pi
```

e abra `http://<IP do Pi>:5000` no navegador do computador ou do celular. O passo a passo de uso (perímetro, Telegram, início automático com o systemd) está no [README](../README.md).

Para ter uma ideia da velocidade: no Pi 3, o MobileNet-SSD processa cerca de 1 imagem por segundo. Isso é esperado e suficiente, porque a detecção de pessoas só roda quando há movimento.

---

## 5. Atualizar depois de mudanças no código

```bash
cd ~/safeguard
git pull
source .venv/bin/activate
pip install -r requirements-pi.txt
python scripts/verificar_ambiente.py
```

Ou simplesmente rode o script de novo: `SKIP_UPGRADE=1 bash scripts/setup_raspberry_pi.sh`.

---

## 6. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `error: externally-managed-environment` ao usar `pip` | O Raspberry Pi OS não deixa usar o `pip` fora de um ambiente virtual | Ative o ambiente: `source .venv/bin/activate` |
| `module 'cv2.dnn' has no attribute 'readNetFromCaffe'` | Um OpenCV 5 instalado pelo `pip` está escondendo o do `apt` | `pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python` (com o `.venv` ativo) |
| `numpy.core.multiarray failed to import` ou erro de versão do NumPy | Um NumPy instalado pelo `pip` no `.venv` não combina com o OpenCV do `apt` | `pip uninstall -y numpy` (com o `.venv` ativo) |
| `ModuleNotFoundError: No module named 'cv2'` | O `.venv` foi criado sem `--system-site-packages` | `rm -rf .venv` e recrie como na seção 3.4 |
| `ModuleNotFoundError: No module named 'server'` | Script executado como arquivo, ou fora da raiz do projeto | Rode da pasta `~/safeguard` com `python -m server.<script>` |
| Erro `blobs.size() >= 2` | `.prototxt` e `.caffemodel` vieram de fontes diferentes | Apague os dois e baixe de novo (seção 3.5) |
| `.caffemodel` com poucos KB | Download interrompido | Apague o arquivo e baixe de novo |
| "Não foi possível abrir a câmera" | Índice errado, usuário fora do grupo `video` ou câmera não reconhecida | `v4l2-ctl --list-devices`, `groups`, ajuste `CAMERA_INDEX` no `.env` |
| "cannot connect to X server" / "could not connect to display" | Script com janela (`cv2.imshow`) rodando pelo SSH | Use os scripts sem janela (seção 4) ou rode no Pi com monitor |
| `/bin/bash^M: bad interpreter` | O `.sh` foi salvo no Windows com fim de linha CRLF | `sed -i 's/\r$//' scripts/setup_raspberry_pi.sh` |
| "Arquivo de perímetro inválido" | `perimeter.json` vazio ou salvo com BOM | Apague o arquivo para vigiar a imagem inteira |
| Pi travando ou `vcgencmd get_throttled` diferente de `0x0` | Fonte fraca ou superaquecimento | Fonte de 5 V / 2,5 A e dissipador |
