/**
 * Desenho e edição do polígono do perímetro sobre um <canvas>.
 *
 * Fluxo:
 *   1. Carrega a imagem de referência (/snapshot) e o perímetro salvo
 *      (GET /api/perimetro). O canvas cobre exatamente a imagem.
 *   2. Clique adiciona vértice; arrastar move; botão direito remove.
 *   3. "Salvar perímetro" envia via POST /api/perimetro.
 *
 * Os pontos são mantidos NORMALIZADOS (0.0-1.0) o tempo todo: só viram
 * pixels na hora de desenhar. Assim o tamanho em que a imagem aparece na
 * tela não importa -- ver perimeter.py no servidor para o porquê.
 */
(() => {
  const IMAGEM_INTEIRA = [[0, 0], [1, 0], [1, 1], [0, 1]];
  const RAIO_VERTICE = 7;
  const RAIO_ALCANCE = 14; // distância (px) para "pegar" um vértice

  const img = document.getElementById("snapshot");
  const canvas = document.getElementById("perimetro-canvas");
  const ctx = canvas.getContext("2d");
  const msg = document.getElementById("perimetro-msg");

  let pontos = [];       // [[x, y], ...] normalizados
  let salvos = [];       // último estado salvo no servidor
  let arrastando = -1;   // índice do vértice sendo arrastado

  function mostrar(texto, tipo = "") {
    msg.textContent = texto;
    msg.className = "msg " + tipo;
  }

  function alterado() {
    return JSON.stringify(pontos) !== JSON.stringify(salvos);
  }

  function atualizarAviso() {
    if (alterado()) mostrar("Alterações não salvas.", "pendente");
    else if (msg.classList.contains("pendente")) mostrar("");
  }

  // --- Canvas ----------------------------------------------------------
  function ajustarCanvas() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(img.clientWidth * dpr);
    canvas.height = Math.round(img.clientHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    desenhar();
  }

  function paraPixels([x, y]) {
    return [x * img.clientWidth, y * img.clientHeight];
  }

  function desenhar() {
    const w = img.clientWidth;
    const h = img.clientHeight;
    ctx.clearRect(0, 0, w, h);
    if (pontos.length === 0) return;

    const px = pontos.map(paraPixels);

    // Escurece o que fica FORA do perímetro (regra evenodd: retângulo menos polígono).
    if (pontos.length >= 3) {
      ctx.beginPath();
      ctx.rect(0, 0, w, h);
      px.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
      ctx.closePath();
      ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
      ctx.fill("evenodd");
    }

    ctx.beginPath();
    px.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    if (pontos.length >= 3) ctx.closePath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#00c8ff";
    ctx.stroke();

    px.forEach(([x, y], i) => {
      ctx.beginPath();
      ctx.arc(x, y, RAIO_VERTICE, 0, Math.PI * 2);
      ctx.fillStyle = i === arrastando ? "#ffd400" : "#00c8ff";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#000";
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px system-ui, sans-serif";
      ctx.fillText(String(i + 1), x + 9, y - 9);
    });
  }

  // --- Interação -------------------------------------------------------
  function posicaoNormalizada(evento) {
    const r = canvas.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (evento.clientX - r.left) / r.width));
    const y = Math.min(1, Math.max(0, (evento.clientY - r.top) / r.height));
    return [Number(x.toFixed(4)), Number(y.toFixed(4))];
  }

  function verticeProximo(evento) {
    const r = canvas.getBoundingClientRect();
    const ex = evento.clientX - r.left;
    const ey = evento.clientY - r.top;
    let melhor = -1;
    let menor = RAIO_ALCANCE;
    pontos.forEach((p, i) => {
      const [x, y] = paraPixels(p);
      const d = Math.hypot(x - ex, y - ey);
      if (d <= menor) { menor = d; melhor = i; }
    });
    return melhor;
  }

  canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const i = verticeProximo(e);
    if (i >= 0) {
      arrastando = i;
      canvas.setPointerCapture(e.pointerId);
    } else {
      pontos.push(posicaoNormalizada(e));
    }
    desenhar();
    atualizarAviso();
  });

  canvas.addEventListener("pointermove", (e) => {
    if (arrastando < 0) {
      canvas.style.cursor = verticeProximo(e) >= 0 ? "grab" : "crosshair";
      return;
    }
    pontos[arrastando] = posicaoNormalizada(e);
    desenhar();
  });

  function soltar() {
    if (arrastando < 0) return;
    arrastando = -1;
    desenhar();
    atualizarAviso();
  }
  canvas.addEventListener("pointerup", soltar);
  canvas.addEventListener("pointercancel", soltar);

  canvas.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    const i = verticeProximo(e);
    if (i >= 0) pontos.splice(i, 1);
    desenhar();
    atualizarAviso();
  });

  // --- Botões ----------------------------------------------------------
  document.getElementById("desfazer").addEventListener("click", () => {
    pontos.pop();
    desenhar();
    atualizarAviso();
  });

  document.getElementById("limpar").addEventListener("click", () => {
    pontos = [];
    desenhar();
    atualizarAviso();
  });

  document.getElementById("perimetro-total").addEventListener("click", () => {
    pontos = IMAGEM_INTEIRA.map((p) => [...p]);
    desenhar();
    atualizarAviso();
  });

  document.getElementById("nova-imagem").addEventListener("click", carregarImagem);

  document.getElementById("salvar-perimetro").addEventListener("click", async () => {
    if (pontos.length < 3) {
      mostrar("O perímetro precisa de pelo menos 3 pontos.", "erro");
      return;
    }
    try {
      const resp = await fetch("/api/perimetro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pontos }),
      });
      const corpo = await resp.json();
      if (!resp.ok) throw new Error(corpo.erro || `HTTP ${resp.status}`);
      salvos = corpo.pontos;
      pontos = corpo.pontos.map((p) => [...p]);
      desenhar();
      mostrar(`Perímetro salvo (${pontos.length} pontos). Já vale no monitoramento.`, "ok");
    } catch (err) {
      mostrar("Erro ao salvar: " + err.message, "erro");
    }
  });

  // Avisa antes de sair da página com alterações pendentes.
  window.addEventListener("beforeunload", (e) => {
    if (alterado()) e.preventDefault();
  });

  // --- Carga inicial ---------------------------------------------------
  function carregarImagem() {
    // Query string evita que o navegador reaproveite um snapshot antigo.
    img.src = "/snapshot?t=" + Date.now();
  }

  img.addEventListener("load", ajustarCanvas);
  img.addEventListener("error", () => {
    // 503 = o pipeline ainda não tem frame; tenta de novo em instantes.
    mostrar("Aguardando imagem da câmera...", "pendente");
    setTimeout(carregarImagem, 1500);
  });
  new ResizeObserver(ajustarCanvas).observe(img);

  async function carregarPerimetro() {
    try {
      const resp = await fetch("/api/perimetro");
      const corpo = await resp.json();
      salvos = corpo.pontos;
      pontos = corpo.pontos.map((p) => [...p]);
      desenhar();
    } catch (err) {
      mostrar("Não foi possível carregar o perímetro salvo.", "erro");
    }
  }

  carregarImagem();
  carregarPerimetro();
})();
