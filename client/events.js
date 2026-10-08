/**
 * Monitoramento: estado do pipeline (GET /api/status), histórico de
 * eventos (GET /api/eventos) e aviso em tempo real de invasão via
 * Socket.IO (evento "intrusao", emitido pelo app.py).
 *
 * Se o cliente do Socket.IO não carregar (ex.: Pi sem internet para o
 * CDN), a lista continua sendo atualizada por consulta periódica.
 */
(() => {
  const INTERVALO_STATUS_MS = 2000;
  const INTERVALO_EVENTOS_MS = 15000;
  const DURACAO_ALERTA_MS = 15000;

  const statusEl = document.getElementById("status");
  const lista = document.getElementById("lista-eventos");
  const alerta = document.getElementById("alerta");
  const video = document.getElementById("video");

  // --- Estado do pipeline ---------------------------------------------
  async function atualizarStatus() {
    try {
      const s = await (await fetch("/api/status")).json();
      if (s.running) {
        let texto = "Monitorando";
        if (s.cooldown_remaining > 0) texto += ` · cooldown ${Math.ceil(s.cooldown_remaining)}s`;
        statusEl.textContent = texto;
        statusEl.className = "pill ok";
      } else {
        statusEl.textContent = "Parado" + (s.error ? `: ${s.error}` : "");
        statusEl.className = "pill erro";
      }
    } catch {
      statusEl.textContent = "Servidor fora do ar";
      statusEl.className = "pill erro";
    }
  }

  // --- Histórico -------------------------------------------------------
  function formatarHora(iso) {
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString("pt-BR");
  }

  function criarItem(evento) {
    const li = document.createElement("li");

    const hora = document.createElement("div");
    hora.className = "evento-hora";
    hora.textContent = formatarHora(evento.timestamp);
    li.appendChild(hora);

    const mini = document.createElement("div");
    mini.className = "miniaturas";
    for (const src of evento.imagens) {
      const a = document.createElement("a");
      a.href = src;
      a.target = "_blank";
      a.rel = "noopener";
      const im = document.createElement("img");
      im.src = src;
      im.loading = "lazy";
      im.alt = "Imagem do evento";
      a.appendChild(im);
      mini.appendChild(a);
    }
    li.appendChild(mini);
    return li;
  }

  async function carregarEventos() {
    try {
      const { eventos } = await (await fetch("/api/eventos")).json();
      lista.replaceChildren(...eventos.map(criarItem));
      if (eventos.length === 0) {
        const li = document.createElement("li");
        li.className = "vazio";
        li.textContent = "Nenhum evento registrado ainda.";
        lista.appendChild(li);
      }
    } catch {
      // Mantém a lista atual; a próxima consulta tenta de novo.
    }
  }

  // --- Alerta em tempo real -------------------------------------------
  let timerAlerta = null;
  function mostrarAlerta(texto) {
    alerta.textContent = texto;
    alerta.hidden = false;
    clearTimeout(timerAlerta);
    timerAlerta = setTimeout(() => (alerta.hidden = true), DURACAO_ALERTA_MS);
  }

  if (typeof io !== "undefined") {
    const socket = io();
    socket.on("intrusao", (evento) => {
      mostrarAlerta(evento.mensagem || "Invasão detectada!");
      carregarEventos();
    });
  }

  // --- Vídeo: reconecta se o stream cair -------------------------------
  video.addEventListener("error", () => {
    setTimeout(() => (video.src = "/video_feed?t=" + Date.now()), 3000);
  });

  atualizarStatus();
  carregarEventos();
  setInterval(atualizarStatus, INTERVALO_STATUS_MS);
  setInterval(carregarEventos, INTERVALO_EVENTOS_MS);
})();
