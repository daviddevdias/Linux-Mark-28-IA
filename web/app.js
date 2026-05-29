"use strict";

let jarvis = null;
const domCache = {};
window.wxAnimFrame = null;

function getEl(id) {
  if (!domCache[id]) domCache[id] = document.getElementById(id);
  return domCache[id];
}

new QWebChannel(qt.webChannelTransport, (channel) => {
  jarvis = channel.objects.jarvis;
  jarvis.dados_para_ui.connect(receberDoJarvis);
  inicializar();
});

window.receberDoJarvis = function (raw) {
  try {
    const d = typeof raw === "string" ? JSON.parse(raw) : raw;
    processar(d);
  } catch (e) { }
};

function processar(d) {
  if (d.cpu !== undefined) {
    atualizarMetrica("cpu", d.cpu);
  }
  if (d.ram !== undefined) {
    atualizarMetrica("ram", d.ram);
  }
  if (d.resposta !== undefined) {
    adicionarMensagem("ai", d.resposta);
  }
  if (d.erro !== undefined) {
    adicionarMensagem("ai", "⚠ " + d.erro);
  }
  if (d.ia_status !== undefined) {
    atualizarIAStatus(d.ia_status);
  }
  if (d.clima_dados !== undefined) {
    parseWeatherData(d.clima_dados, d.cidade_buscada);
  }
  if (d.visao_status !== undefined) {
    getEl("vision-status").textContent = d.visao_status;
  }
  if (d.visao_erro !== undefined) {
    getEl("vision-status").textContent = "⚠ " + d.visao_erro;
  }
  if (d.visao_img !== undefined) {
    const c = getEl("vision-img-container");
    if (c) {
      c.classList.add("visible");
      getEl("vision-img").src = "data:image/png;base64," + d.visao_img;
    }
  }
  if (d.visao_resultado !== undefined) {
    const r = getEl("vision-result");
    if (r) {
      r.classList.add("visible");
      r.textContent = d.visao_resultado;
    }
  }
  if (d.voz_speaking !== undefined) {
    const wave = getEl("speaking-wave");
    if (wave) wave.classList.toggle("active", d.voz_speaking);
  }
  if (d.monitor_evento !== undefined) {
    adicionarEventoMonitor(d.monitor_evento);
  }
  if (d.monitor_alerta !== undefined) {
    adicionarMensagem("ai", "⚠ " + d.monitor_alerta);
  }
  if (d.monitor_dica !== undefined) {
    adicionarMensagem("ai", "◈ " + d.monitor_dica);
  }
  if (d.aguardando_confirmacao) {
    adicionarMensagem("ai", 'Diga "pode ajudar" ou "dispensa ajuda".');
  }
  if (d.temas !== undefined) {
    state.themes = d.temas;
    if (state.page === "temas") renderSecao("temas");
  }
  if (d.tema_ativo !== undefined) {
    applyTheme(d.tema_ativo);
    state.theme = d.tema_ativo;
  }
  if (d.alarmes !== undefined) {
    try {
      state.alarmes.lista = Array.isArray(d.alarmes)
        ? d.alarmes
        : JSON.parse(d.alarmes);
      if (currentSection === "alarms") renderSecaoAlarmes();
    } catch (e) { }
  }
}

const state = {
  page: "chat",
  theme: "LARANJA_MESA",
  themes: {},
  configEdit: false,
  apis: {},
  weather: { city: "", norm: null, error: null },
  alarmes: { lista: [], filtro: "todos" },
};

let currentSection = "chat";

function inicializar() {
  getEl("chat-init-ts").textContent = agora();

  jarvis.obter_configuracoes_atuais((raw) => {
    const c = JSON.parse(raw);
    Object.assign(state.apis, c);

    setVal("cfg-nome-mestre", c.nome_mestre || "");
    setVal("cfg-cidade-padrao", c.cidade_padrao || "");
    setVal("cfg-voz", c.voz || "");
    setVal("cfg-whisper-model", c.whisper_model || "small");
    setVal("cfg-gemini", c.gemini || "");
    setVal("cfg-qwen", c.qwen || "");
    setVal("cfg-weather", c.openweather_api_key || "");
    setVal("cfg-tg-token", c.telegram_token || "");
    setVal("cfg-tg-auth", c.telegram_auth_token || "");
    setVal("cfg-spotify-id", c.spotify_id || "");
    setVal("cfg-spotify-sec", c.spotify_sec || "");
    setVal("cfg-st-token", c.smartthings || "");
    setVal("cfg-st-tv-id", c.smartthings_tv_id || "");
    setVal("cfg-deepgram", c.deepgram_api_key || "");
    setVal("cfg-openai", c.openai_api_key || "");
    setVal("cfg-openai-tts", c.openai_tts_voice || "nova");
    setVal("cfg-fish", c.fish_audio_api_key || "");
    setVal("cfg-fish-id", c.fish_audio_voice_id || "");
    setVal("cfg-notas", c.notas || "");

    const modo = c.ia_mode || "ollama";
    document.querySelectorAll(".btn-ia-mode").forEach((b) => {
      b.classList.toggle(
        "active",
        b.textContent.trim().toLowerCase() === modo.toLowerCase(),
      );
    });

    state.weather.city = c.cidade_padrao || "São Paulo";
    state.apis.cidade_padrao = state.weather.city;

    if (c.tema_ativo && c.tema_ativo !== state.theme) {
      state.theme = c.tema_ativo;
      applyTheme(c.tema_ativo);
    }
    if (c.temas) state.themes = c.temas;
  });

  jarvis.obter_config_voz((raw) => {
    const v = JSON.parse(raw);
    const sel = getEl("cfg-device-index");
    if (sel) {
      sel.innerHTML = "";
      (v.microfones || []).forEach((m, i) => {
        const opt = document.createElement("option");
        opt.value = i;
        opt.textContent = m;
        if (i === v.device_index) opt.selected = true;
        sel.appendChild(opt);
      });
      if (sel.options.length === 0) {
        const opt = document.createElement("option");
        opt.value = v.device_index || 1;
        opt.textContent = `Microfone ${v.device_index || 1}`;
        sel.appendChild(opt);
      }
    }
  });

  if (jarvis.obter_alarmes) {
    jarvis.obter_alarmes((raw) => {
      try {
        const lista = JSON.parse(raw);
        if (Array.isArray(lista)) state.alarmes.lista = lista;
      } catch (e) { }
    });
  }

  carregarComandos();
  atualizarStatusIA();
  iniciarVerificadorAlarmes();
}

const NAV_LABELS = {
  chat: "CHAT",
  config: "CONFIGURAÇÕES",
  commands: "COMANDOS",
  alarms: "ALARMES",
  weather: "CLIMA",
  vision: "VISÃO",
  status: "STATUS",
  temas: "PROTOCOLO VISUAL",
};

function switchTab(name) {
  currentSection = name;
  document
    .querySelectorAll(".section")
    .forEach((s) => s.classList.remove("active"));
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.remove("active"));

  const sec = getEl("section-" + name);
  if (sec) sec.classList.add("active");

  const nav = document.querySelector(`.nav-item[data-section="${name}"]`);
  if (nav) nav.classList.add("active");

  const label = getEl("topbar-name");
  if (label) label.textContent = NAV_LABELS[name] || name.toUpperCase();

  if (name === "alarms") renderSecaoAlarmes();
  if (name === "weather") renderSecaoClima();
  if (name === "config") renderSecaoConfig();
  if (name === "temas") renderSecaoTemas();
}
window.switchTab = switchTab;

function enviarChat() {
  const inp = getEl("chat-input");
  if (!inp) return;
  const txt = inp.value.trim();
  if (!txt || !jarvis) return;
  adicionarMensagem("user", txt);
  inp.value = "";
  inp.style.height = "auto";
  jarvis.executar_comando(txt);
}
window.enviarChat = enviarChat;

function adicionarMensagem(role, texto) {
  const msgs = getEl("chat-messages");
  if (!msgs) return;
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const av = document.createElement("div");
  av.className = "msg-avatar";
  av.textContent = role === "user" ? "U" : "J";
  const content = document.createElement("div");
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = texto;
  const ts = document.createElement("div");
  ts.className = "msg-ts";
  ts.textContent = agora();
  content.appendChild(bubble);
  content.appendChild(ts);
  div.appendChild(av);
  div.appendChild(content);
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

getEl("chat-input")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    enviarChat();
  }
});
getEl("chat-input")?.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 100) + "px";
});

function salvarCampo(chave, inputId, btn) {
  if (!jarvis) return;
  const el = getEl(inputId);
  if (!el) return;
  const val = el.value;
  jarvis.salvar_configuracao(chave, val);
  if (chave === "cidade_padrao") {
    state.weather.city = val;
    state.apis.cidade_padrao = val;
  }
  if (chave === "nome_mestre") {
    state.apis.nome_mestre = val;
  }
  btn.textContent = "✓ OK";
  btn.classList.add("saved");
  setTimeout(() => {
    btn.textContent = "SALVAR";
    btn.classList.remove("saved");
  }, 1800);
  showToast("SALVO: " + chave.toUpperCase());
}
window.salvarCampo = salvarCampo;

function salvarMic() {
  if (!jarvis) return;
  const sel = getEl("cfg-device-index");
  if (sel) jarvis.salvar_configuracao("device_index", sel.value);
  showToast("MICROFONE SALVO");
}
window.salvarMic = salvarMic;

function testarVoz() {
  if (jarvis) jarvis.testar_voz_painel();
  showToast("TESTANDO SÍNTESE...");
}
window.testarVoz = testarVoz;

function alternarIA(modo) {
  if (!jarvis) return;
  jarvis.alternar_ia(modo);
  document.querySelectorAll(".btn-ia-mode").forEach((b) => {
    b.classList.toggle(
      "active",
      b.textContent.trim().toLowerCase() === modo.toLowerCase(),
    );
  });
  showToast("MODO IA: " + modo.toUpperCase());
}
window.alternarIA = alternarIA;

function atualizarStatusIA() {
  if (!jarvis) return;
  jarvis.obter_ia_status((raw) => {
    try {
      atualizarIAStatus(JSON.parse(raw));
    } catch (e) { }
  });
}

function atualizarIAStatus(s) {
  const dot = getEl("ia-dot");
  const lbl = getEl("ia-mode-label");
  const sdot = getEl("ia-status-dot");
  const bkval = getEl("ia-backend-val");
  const mdval = getEl("ia-model-val");
  if (!s) return;
  const online = s.online !== false;
  if (dot) {
    dot.className = "dot" + (online ? "" : " red");
  }
  if (sdot) {
    sdot.style.background = online ? "var(--accent)" : "var(--danger)";
    sdot.style.boxShadow = `0 0 8px ${online ? "var(--accent)" : "var(--danger)"}`;
  }
  if (lbl) lbl.textContent = (s.modo || s.backend || "OFFLINE").toUpperCase();
  if (bkval) bkval.textContent = (s.backend || "--").toUpperCase();
  if (mdval) mdval.textContent = s.modelo || s.model || "--";
}

function carregarComandos() {
  if (!jarvis) return;
  jarvis.obter_comandos((raw) => {
    try {
      window._allComandos = JSON.parse(raw);
      renderCatFilter();
      renderComandos(window._allComandos);
    } catch (e) { }
  });
}

function renderCatFilter() {
  const cats = [
    ...new Set((window._allComandos || []).map((c) => c.cat).filter(Boolean)),
  ];
  const el = getEl("cat-filter");
  if (!el) return;
  el.innerHTML = ["TODOS", ...cats]
    .map(
      (c) => `
    <button class="btn-cat ${c === "TODOS" ? "active" : ""}"
            onclick="filtrarPorCat(this,'${escHtml(c)}')">${escHtml(c)}</button>
  `,
    )
    .join("");
}

function filtrarPorCat(btn, cat) {
  document
    .querySelectorAll(".btn-cat")
    .forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  const lista =
    cat === "TODOS"
      ? window._allComandos
      : (window._allComandos || []).filter((c) => c.cat === cat);
  renderComandos(lista);
}
window.filtrarPorCat = filtrarPorCat;

function filtrarComandos() {
  const q = getEl("cmd-search")?.value.toLowerCase().trim() || "";
  let lista = window._allComandos || [];
  if (q)
    lista = lista.filter(
      (c) =>
        c.cmd.toLowerCase().includes(q) ||
        c.desc.toLowerCase().includes(q) ||
        (c.passos || []).some((p) => p.toLowerCase().includes(q)),
    );
  renderComandos(lista);
}
window.filtrarComandos = filtrarComandos;

function renderComandos(lista) {
  const el = getEl("commands-list");
  if (!el) return;
  if (!lista.length) {
    el.innerHTML = '<div class="empty-state">NENHUM COMANDO ENCONTRADO</div>';
    return;
  }
  el.innerHTML = lista
    .map(
      (c) => `
    <div class="cmd-card" onclick="enviarComandoChat('${escHtml(c.handler || c.cmd)}')">
      <div class="cmd-card-top">
        <span class="cmd-icon">${c.icon || "◇"}</span>
        <span class="cmd-name">${escHtml(c.cmd)}</span>
        <span class="cmd-cat-badge">${escHtml(c.cat)}</span>
      </div>
      <div class="cmd-desc">${escHtml(c.desc)}</div>
      <div class="cmd-steps">${(c.passos || [])
          .slice(0, 5)
          .map((p) => `<span class="cmd-step">${escHtml(p)}</span>`)
          .join("")}</div>
    </div>
  `,
    )
    .join("");
}

function enviarComandoChat(cmd) {
  switchTab("chat");
  const inp = getEl("chat-input");
  if (inp) {
    inp.value = cmd;
    enviarChat();
  }
}
window.enviarComandoChat = enviarComandoChat;

function renderSecaoAlarmes() {
  const wrap = getEl("section-alarms");
  if (!wrap) return;

  const alarmes = state.alarmes.lista || [];
  const pendentes = alarmes.filter((a) => a.status === "pendente");
  const concluidos = alarmes.filter((a) => a.status === "concluido");
  const filtro = state.alarmes.filtro || "todos";
  const visiveis =
    filtro === "pendentes"
      ? pendentes
      : filtro === "concluidos"
        ? concluidos
        : alarmes;

  wrap.innerHTML = `
  <div class="alm-shell">
    <div class="alm-header">
      <div>
        <div class="alm-title">⏰ CENTRAL DE ALARMES</div>
        <div class="alm-sub">Agendamento · Alertas · Soneca · Controle total</div>
      </div>
      <button class="alm-new-btn" onclick="abrirModalNovoAlarme()">＋ NOVO ALARME</button>
    </div>

    <div class="alm-stats">
      <div class="alm-stat" style="border-color:var(--accent2)33;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent2);border-radius:12px 12px 0 0;"></div>
        <div class="alm-stat-lbl">⏰ ATIVOS</div>
        <div class="alm-stat-val" style="color:var(--accent2);">${pendentes.length}</div>
      </div>
      <div class="alm-stat" style="border-color:var(--accent)33;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent);border-radius:12px 12px 0 0;"></div>
        <div class="alm-stat-lbl">◈ TOTAL</div>
        <div class="alm-stat-val" style="color:var(--accent);">${alarmes.length}</div>
      </div>
      <div class="alm-stat" style="border-color:rgba(255,255,255,0.1);">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:rgba(255,255,255,0.2);border-radius:12px 12px 0 0;"></div>
        <div class="alm-stat-lbl">✅ CONCLUÍDOS</div>
        <div class="alm-stat-val" style="color:rgba(255,255,255,0.4);">${concluidos.length}</div>
      </div>
    </div>

    <div class="alm-quick">
      <div class="alm-quick-title">NOVO ALARME RÁPIDO</div>
      <div class="alm-quick-row">
        <div class="alm-field">
          <div class="alm-label">HORA</div>
          <input class="alm-inp" type="time" id="alarmeHoraRapida">
        </div>
        <div class="alm-field" style="flex:1;min-width:160px;">
          <div class="alm-label">MISSÃO</div>
          <input class="alm-inp" type="text" id="alarmeMissaoRapida" placeholder="Ex: Reunião, Medicação..." maxlength="120">
        </div>
        <div class="alm-field">
          <div class="alm-label">DATA (opcional)</div>
          <input class="alm-inp" type="date" id="alarmeDataRapida">
        </div>
        <button class="alm-create-btn" onclick="criarAlarmeRapido()">▶ CRIAR</button>
      </div>
      <div class="alm-days">
        <span class="alm-label">DIAS:</span>
        ${["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
      .map(
        (d, i) => `
          <label class="alm-day-lbl">
            <input type="checkbox" class="dia-check" data-idx="${i}" style="accent-color:var(--accent);width:18px;height:18px;">
            ${d}
          </label>`,
      )
      .join("")}
        <label class="alm-rep-lbl">
          <input type="checkbox" id="alarmeRepetir" style="accent-color:var(--accent2);width:18px;height:18px;">
          REPETIR
        </label>
      </div>
    </div>

    <div class="alm-list-wrap">
      <div class="alm-list-header">
        <div style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:var(--text-muted);letter-spacing:3px;">LISTA DE ALARMES</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <div class="alm-filter-row">
            ${["todos", "pendentes", "concluidos"]
      .map(
        (f) => `
              <button class="alm-filter-btn ${filtro === f ? "active" : ""}" onclick="filtrarAlarmes('${f}')">${f.toUpperCase()}</button>`,
      )
      .join("")}
          </div>
          <button class="alm-filter-btn" onclick="limparConcluidos()">🗑 LIMPAR</button>
          <button class="alm-filter-btn danger-btn" onclick="pararAlarme()">⏹ PARAR</button>
        </div>
      </div>
      <div class="alm-list" id="alarmesList">
        ${renderAlarmItems(visiveis)}
      </div>
    </div>

    <div class="modal-overlay" id="modalNovoAlarme">
      <div class="modal-box">
        <div class="modal-icon">⏰</div>
        <h3 style="font-family:var(--font-mono);letter-spacing:4px;color:var(--accent);margin-bottom:18px;">NOVO ALARME</h3>
        <div style="display:flex;flex-direction:column;gap:14px;text-align:left;">
          <div>
            <div class="alm-label" style="display:block;margin-bottom:6px;">HORA *</div>
            <input class="alm-inp" type="time" id="modalAlarmeHora">
          </div>
          <div>
            <div class="alm-label" style="display:block;margin-bottom:6px;">MISSÃO</div>
            <input class="alm-inp" type="text" id="modalAlarmeMissao" placeholder="Descrição" maxlength="120">
          </div>
          <div>
            <div class="alm-label" style="display:block;margin-bottom:6px;">DATA (opcional)</div>
            <input class="alm-inp" type="date" id="modalAlarmeData">
          </div>
          <div>
            <div class="alm-label" style="display:block;margin-bottom:8px;">DIAS DA SEMANA</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              ${["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
      .map(
        (d, i) => `
                <label style="display:flex;align-items:center;gap:5px;font-family:var(--font-mono);font-size:11px;color:var(--text-dim);cursor:pointer;">
                  <input type="checkbox" class="modal-dia-check" data-idx="${i}" style="accent-color:var(--accent);width:16px;height:16px;">
                  ${d}
                </label>`,
      )
      .join("")}
            </div>
          </div>
          <label style="display:flex;align-items:center;gap:10px;cursor:pointer;font-family:var(--font-mono);font-size:12px;color:var(--text-dim);">
            <input type="checkbox" id="modalAlarmeRepetir" style="accent-color:var(--accent2);width:16px;height:16px;">
            REPETIR AUTOMATICAMENTE
          </label>
        </div>
        <div style="display:flex;gap:12px;margin-top:22px;">
          <button class="btn-save-field" onclick="confirmarNovoAlarme()" style="flex:1;">◈ CRIAR</button>
          <button class="btn-save-field" onclick="fecharModalAlarme()" style="background:transparent;border-color:var(--border);color:var(--text-muted);">CANCELAR</button>
        </div>
      </div>
    </div>
  </div>`;

  const inp = getEl("alarmeHoraRapida");
  if (inp) inp.value = new Date().toTimeString().slice(0, 5);
  getEl("alarmeMissaoRapida")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") criarAlarmeRapido();
  });
}

function renderAlarmItems(lista) {
  if (!lista || !lista.length)
    return `
    <div class="alm-empty">
      <div style="font-size:40px;margin-bottom:12px;">⏰</div>
      <div>Nenhum alarme nesta categoria.</div>
      <div style="font-size:12px;opacity:.5;margin-top:6px;">Use o formulário acima para criar um alarme.</div>
    </div>`;

  return lista
    .map((a) => {
      const ok = a.status === "pendente";
      const cor = ok ? "var(--accent)" : "rgba(255,255,255,0.3)";
      const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
      const diasStr =
        a.dias_semana && a.dias_semana.length
          ? a.dias_semana.map((d) => DIAS[d]).join(", ")
          : a.data || "Hoje";
      const meta = [diasStr, a.repetir ? "REPETIR" : "", !ok ? "CONCLUÍDO" : ""]
        .filter(Boolean)
        .join(" · ");
      return `
    <div class="alm-item" style="border-left-color:${cor};">
      <div class="alm-time" style="color:${cor};">${escHtml(a.hora)}</div>
      <div class="alm-info">
        <div class="alm-mission">${escHtml(a.missao || "Alarme")}</div>
        <div class="alm-meta">${escHtml(meta)}</div>
      </div>
      ${ok
          ? `
      <div class="alm-actions">
        <button class="alm-btn snooze" onclick="snoozeAlarme('${escHtml(a.hora)}','${escHtml(a.missao || "")}')">💤</button>
        <button class="alm-btn danger" onclick="removerAlarmeState('${escHtml(a.hora)}','${escHtml(a.missao || "")}','${escHtml(a.data || "")}')">✕</button>
      </div>`
          : ""
        }
    </div>`;
    })
    .join("");
}

function abrirModalNovoAlarme() {
  const ov = getEl("modalNovoAlarme");
  if (!ov) return;
  const inp = getEl("modalAlarmeHora");
  if (inp) inp.value = new Date().toTimeString().slice(0, 5);
  ov.classList.add("open");
}
window.abrirModalNovoAlarme = abrirModalNovoAlarme;

function fecharModalAlarme() {
  getEl("modalNovoAlarme")?.classList.remove("open");
}
window.fecharModalAlarme = fecharModalAlarme;

function confirmarNovoAlarme() {
  const hora = getEl("modalAlarmeHora")?.value || "";
  const missao = getEl("modalAlarmeMissao")?.value.trim() || "Alarme";
  const data = getEl("modalAlarmeData")?.value || "";
  const rep = getEl("modalAlarmeRepetir")?.checked || false;
  const dias = [...document.querySelectorAll(".modal-dia-check:checked")].map(
    (el) => parseInt(el.dataset.idx),
  );
  if (!hora) {
    showToast("HORA OBRIGATÓRIA");
    return;
  }
  salvarAlarme({
    hora,
    missao,
    data: data || null,
    repetir: rep,
    dias_semana: dias.length ? dias : null,
  });
  fecharModalAlarme();
}
window.confirmarNovoAlarme = confirmarNovoAlarme;

function criarAlarmeRapido() {
  const hora = getEl("alarmeHoraRapida")?.value || "";
  const missao = getEl("alarmeMissaoRapida")?.value.trim() || "Alarme";
  const data = getEl("alarmeDataRapida")?.value || "";
  const rep = getEl("alarmeRepetir")?.checked || false;
  const dias = [...document.querySelectorAll(".dia-check:checked")].map((el) =>
    parseInt(el.dataset.idx),
  );
  if (!hora) {
    showToast("INFORME A HORA");
    return;
  }
  salvarAlarme({
    hora,
    missao,
    data: data || null,
    repetir: rep,
    dias_semana: dias.length ? dias : null,
  });
  const m = getEl("alarmeMissaoRapida");
  if (m) m.value = "";
  document.querySelectorAll(".dia-check").forEach((c) => (c.checked = false));
  const r = getEl("alarmeRepetir");
  if (r) r.checked = false;
}
window.criarAlarmeRapido = criarAlarmeRapido;

function salvarAlarme({ hora, missao, data, repetir, dias_semana }) {
  const alarme = {
    hora,
    missao,
    status: "pendente",
    repetir: repetir || !!(dias_semana && dias_semana.length),
    criado_em: new Date().toISOString(),
    ultimo_disparo: null,
    data: data || null,
    dias_semana: dias_semana && dias_semana.length ? dias_semana : null,
  };
  state.alarmes.lista.push(alarme);
  if (jarvis?.salvar_alarme) {
    try {
      jarvis.salvar_alarme(JSON.stringify(alarme));
    } catch (e) { }
  }
  showToast(`⏰ ALARME ${hora} CRIADO`);
  if (currentSection === "alarms") renderSecaoAlarmes();
}
window.salvarAlarme = salvarAlarme;

function removerAlarmeState(hora, missao, data) {
  state.alarmes.lista = state.alarmes.lista.filter(
    (a) =>
      !(
        a.hora === hora &&
        a.missao === missao &&
        (a.data || "") === (data || "")
      ),
  );
  if (jarvis?.remover_alarme) {
    try {
      jarvis.remover_alarme(
        JSON.stringify({ hora, missao, data: data || null }),
      );
    } catch (e) { }
  }
  showToast("ALARME REMOVIDO");
  if (currentSection === "alarms") renderSecaoAlarmes();
}
window.removerAlarmeState = removerAlarmeState;

function removerAlarme(idx, hora, missao, data) {
  removerAlarmeState(hora, missao, data);
}
window.removerAlarme = removerAlarme;

function snoozeAlarme(hora, missao) {
  const nova = new Date(Date.now() + 10 * 60000);
  const h = nova.toTimeString().slice(0, 5);
  const d = nova.toISOString().slice(0, 10);
  salvarAlarme({
    hora: h,
    missao: "💤 " + missao,
    data: d,
    repetir: false,
    dias_semana: null,
  });
  showToast(`💤 SONECA: ${h}`);
}
window.snoozeAlarme = snoozeAlarme;

function filtrarAlarmes(f) {
  state.alarmes.filtro = f;
  if (currentSection === "alarms") renderSecaoAlarmes();
}
window.filtrarAlarmes = filtrarAlarmes;

function limparConcluidos() {
  state.alarmes.lista = state.alarmes.lista.filter(
    (a) => a.status !== "concluido",
  );
  if (jarvis?.limpar_alarmes_concluidos) {
    try {
      jarvis.limpar_alarmes_concluidos();
    } catch (e) { }
  }
  showToast("CONCLUÍDOS REMOVIDOS");
  if (currentSection === "alarms") renderSecaoAlarmes();
}
window.limparConcluidos = limparConcluidos;

function pararAlarme() {
  state.alarmes.alarmeAtivo = false;
  if (jarvis?.parar_alarme) {
    try {
      jarvis.parar_alarme();
    } catch (e) { }
  }
  getEl("alarmeNotif")?.remove();
  showToast("ALARME PARADO");
}
window.pararAlarme = pararAlarme;

function iniciarVerificadorAlarmes() {
  if (window.alarmCheckerRunning) return;
  window.alarmCheckerRunning = true;
  setInterval(() => {
    const agora = new Date();
    const hhmm = agora.toTimeString().slice(0, 5);
    const hoje = agora.toISOString().slice(0, 10);
    const diaSem = (agora.getDay() + 6) % 7;
    state.alarmes.lista.forEach((a) => {
      if (a.status !== "pendente" || a.hora !== hhmm) return;
      if (a.data && a.data !== hoje) return;
      if (
        a.dias_semana &&
        a.dias_semana.length &&
        !a.dias_semana.includes(diaSem)
      )
        return;
      a.ultimo_disparo = new Date().toISOString();
      if (!a.repetir) a.status = "concluido";
      mostrarNotificacaoAlarme(a);
    });
  }, 30000);
}

function mostrarNotificacaoAlarme(alarme) {
  let notif = getEl("alarmeNotif");
  if (!notif) {
    notif = document.createElement("div");
    notif.id = "alarmeNotif";
    Object.assign(notif.style, {
      position: "fixed",
      top: "0",
      left: "0",
      right: "0",
      zIndex: "10000",
      background: "linear-gradient(135deg,var(--bg2),var(--panel))",
      borderBottom: "3px solid var(--accent)",
      padding: "16px 28px",
      display: "flex",
      alignItems: "center",
      gap: "18px",
      boxShadow: "0 4px 40px rgba(255,149,0,.3)",
    });
    document.body.appendChild(notif);
  }
  notif.innerHTML = `
    <div style="font-size:28px;">⏰</div>
    <div style="flex:1;">
      <div style="font-family:var(--font-mono);font-size:10px;color:var(--accent);letter-spacing:3px;margin-bottom:3px;">ALARME · ${escHtml(alarme.hora || "")}</div>
      <div style="font-size:15px;color:var(--text);font-weight:700;">${escHtml(alarme.missao || "Alarme")}</div>
    </div>
    <button onclick="snoozeAlarme('${escHtml(alarme.hora)}','${escHtml(alarme.missao || "")}');document.getElementById('alarmeNotif')?.remove();"
            style="background:rgba(255,149,0,0.15);border:1px solid var(--accent);border-radius:3px;color:var(--accent);padding:7px 14px;font-family:var(--font-mono);font-size:11px;cursor:pointer;">💤 10min</button>
    <button onclick="pararAlarme();"
            style="background:transparent;border:1px solid var(--border);border-radius:3px;color:var(--text-muted);padding:7px 14px;font-family:var(--font-mono);font-size:11px;cursor:pointer;">⏹ PARAR</button>`;
}

function renderSecaoClima() {
  const wrap = getEl("section-weather");
  if (!wrap) return;
  const city = state.apis.cidade_padrao || state.weather.city || "São Paulo";
  state.weather.city = city;

  wrap.innerHTML = `
  <div class="wx-root">
    <div class="wx-topbar">
      <div class="wx-search-wrap">
        <input class="wx-input" id="wxCity" placeholder="Buscar cidade..." value="${escHtml(city)}" autocomplete="off">
      </div>
      <button class="btn-save-field" onclick="buscarClima()">BUSCAR</button>
      <button class="btn-save-field" style="background:transparent;border-color:var(--border);color:var(--text-muted);" onclick="atualizarClima()">↺ ATUALIZAR</button>
      <div id="wxSourceBadge"></div>
    </div>
    <div id="wxMain" style="flex:1;min-height:0;display:flex;flex-direction:column;gap:16px;overflow-y:auto;"></div>
  </div>`;

  getEl("wxCity")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") buscarClima();
  });

  if (state.weather.norm) renderWeatherFull(state.weather.norm);
  else fetchWeather(city);
}

function wxIcon(desc) {
  if (!desc) return "🌡️";
  const d = desc.toLowerCase();
  const map = [
    ["thunder", "⛈️"],
    ["storm", "⛈️"],
    ["blizzard", "🌨️"],
    ["snow", "❄️"],
    ["sleet", "🌨️"],
    ["fog", "🌫️"],
    ["mist", "🌫️"],
    ["haze", "🌫️"],
    ["drizzle", "🌦️"],
    ["rain", "🌧️"],
    ["overcast", "☁️"],
    ["partly", "⛅"],
    ["cloud", "⛅"],
    ["clear", "☀️"],
    ["sunny", "☀️"],
    ["tornado", "🌪️"],
    ["wind", "💨"],
  ];
  for (const [k, v] of map) if (d.includes(k)) return v;
  return "🌡️";
}

function wxConditionKey(desc) {
  if (!desc) return "clear";
  const d = desc.toLowerCase();
  if (d.includes("thunder") || d.includes("storm")) return "storm";
  if (d.includes("snow") || d.includes("blizzard") || d.includes("sleet"))
    return "snow";
  if (d.includes("rain") || d.includes("drizzle")) return "rain";
  if (d.includes("fog") || d.includes("mist") || d.includes("haze"))
    return "fog";
  if (d.includes("cloud") || d.includes("overcast")) return "cloudy";
  return "clear";
}

function normalizeWeather(raw, cityFallback) {
  if (!raw || raw.error) return null;
  if (raw.current_condition && raw.current_condition[0]) {
    const cur = raw.current_condition[0];
    const area = (raw.nearest_area && raw.nearest_area[0]) || {};
    const cn = area.areaName?.[0]?.value || cityFallback || "";
    const co = area.country?.[0]?.value || "";
    const rawDesc = cur.weatherDesc?.[0]?.value || "";
    const ptDesc = cur.lang_pt?.[0]?.value || rawDesc;
    const forecast = (raw.weather || []).slice(0, 6).map((d) => {
      const h = d.hourly && d.hourly[4];
      const fd = h?.weatherDesc?.[0]?.value || "";
      const fp = h?.lang_pt?.[0]?.value || fd;
      return {
        date: d.date || "",
        hi: parseInt(d.maxtempC) || 0,
        lo: parseInt(d.mintempC) || 0,
        desc: fp || fd,
        rain: parseFloat(h?.precipMM || 0),
        chanceRain: parseInt(h?.chanceofrain || 0),
      };
    });
    return {
      city: cn,
      country: co,
      temp: parseInt(cur.temp_C) || 0,
      feels: parseInt(cur.FeelsLikeC) || 0,
      desc: ptDesc || rawDesc,
      icon: wxIcon(rawDesc),
      condition: wxConditionKey(rawDesc),
      humidity: parseInt(cur.humidity) || 0,
      wind: parseInt(cur.windspeedKmph) || 0,
      windDir: cur.winddir16Point || "",
      uv: parseInt(cur.uvIndex) || 0,
      pressure: parseInt(cur.pressure) || 0,
      vis: parseInt(cur.visibility) || 0,
      cloud: parseInt(cur.cloudcover) || 0,
      forecast,
      source: "wttr",
    };
  }
  if (raw.main?.temp !== undefined) {
    const desc = raw.weather?.[0]?.description || "N/A";
    const degToCard = (deg) => {
      if (deg == null) return "";
      return ["N", "NE", "L", "SE", "S", "SO", "O", "NO"][
        Math.round(deg / 45) % 8
      ];
    };
    return {
      city: raw.name || cityFallback || "",
      country: raw.sys?.country || "",
      temp: Math.round(raw.main.temp),
      feels: Math.round(raw.main.feels_like || raw.main.temp),
      desc,
      icon: wxIcon(desc),
      condition: wxConditionKey(desc),
      humidity: raw.main.humidity || 0,
      wind: Math.round((raw.wind?.speed || 0) * 3.6),
      windDir: degToCard(raw.wind?.deg),
      uv: 0,
      pressure: raw.main.pressure || 0,
      vis: Math.round((raw.visibility || 0) / 1000),
      cloud: raw.clouds?.all || 0,
      forecast: [],
      source: "owm",
    };
  }
  return null;
}

function buscarClima() {
  const city = (getEl("wxCity")?.value || "").trim();
  if (!city) return;
  state.weather.city = city;
  state.weather.norm = null;
  state.weather.error = null;
  if (jarvis) jarvis.salvar_configuracao("cidade_padrao", city);
  state.apis.cidade_padrao = city;
  fetchWeather(city);
}
window.buscarClima = buscarClima;

function atualizarClima() {
  state.weather.norm = null;
  state.weather.error = null;
  fetchWeather(state.apis.cidade_padrao || state.weather.city || "São Paulo");
}
window.atualizarClima = atualizarClima;

async function fetchWeather(city) {
  const el = getEl("wxMain");
  if (el)
    el.innerHTML = `
    <div class="wx-loading">
      <div class="wx-loading-rings"><div class="wx-ring"></div><div class="wx-ring"></div><div class="wx-ring"></div></div>
      <div class="wx-loading-txt">CONSULTANDO SATÉLITE METEOROLÓGICO</div>
    </div>`;

  if (jarvis) {
    jarvis.solicitar_clima(city);
    return;
  }

  try {
    const url = `https://wttr.in/${encodeURIComponent(city)}?format=j1&lang=pt`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    parseWeatherData(data, city);
  } catch (e) {
    if (el)
      el.innerHTML = `
      <div class="wx-loading">
        <div style="font-size:48px">🌐</div>
        <div style="font-family:var(--font-mono);color:var(--danger);font-size:12px;letter-spacing:3px;">ERRO AO BUSCAR DADOS</div>
        <div style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;">${escHtml(e.message)}</div>
      </div>`;
  }
}
window.fetchWeather = fetchWeather;

function parseWeatherData(raw, city) {
  try {
    const norm = normalizeWeather(
      raw,
      city || state.weather.city || "São Paulo",
    );
    if (!norm) {
      renderWeatherError(raw?.error || "Dados inválidos.");
      return;
    }
    state.weather.norm = norm;
    state.weather.city = norm.city || city;
    state.weather.error = null;
    const inp = getEl("wxCity");
    if (inp && norm.city) inp.value = norm.city;
    renderWeatherFull(norm);
  } catch (e) {
    renderWeatherError("Erro: " + e.message);
  }
}
window.parseWeatherData = parseWeatherData;

function renderClima(d, cidade) {
  parseWeatherData(d, cidade);
}
window.renderClima = renderClima;

function renderWeatherError(msg) {
  const el = getEl("wxMain");
  if (!el) return;
  el.innerHTML = `
    <div class="wx-loading">
      <div style="font-size:48px">🌐</div>
      <div style="font-family:var(--font-mono);font-size:13px;color:var(--danger);letter-spacing:3px;">${escHtml(msg || "Erro desconhecido")}</div>
      <button class="btn-save-field" onclick="atualizarClima()">↺ TENTAR NOVAMENTE</button>
    </div>`;
}

function renderWeatherFull(wx) {
  const el = getEl("wxMain");
  if (!el) return;

  const tCol =
    wx.temp > 35
      ? "var(--danger)"
      : wx.temp > 28
        ? "var(--accent2)"
        : wx.temp > 18
          ? "var(--accent)"
          : "#7eb8ff";
  const uvLbl =
    wx.uv <= 2
      ? "BAIXO"
      : wx.uv <= 5
        ? "MODERADO"
        : wx.uv <= 7
          ? "ALTO"
          : "EXTREMO";
  const uvCol =
    wx.uv <= 2 ? "#00e676" : wx.uv <= 5 ? "#ffd700" : "var(--danger)";
  const DOWS = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];
  const today = new Date();

  const forecastHTML = wx.forecast.length
    ? wx.forecast
      .map((d, i) => {
        const dt = d.date
          ? new Date(d.date + "T12:00:00")
          : new Date(today.getTime() + i * 86400000);
        const dow = i === 0 ? "HOJE" : DOWS[dt.getDay()];
        return `
    <div class="wx-fc">
      <div class="wx-fc-dow">${dow}</div>
      <div class="wx-fc-icon">${wxIcon(d.desc)}</div>
      <div class="wx-fc-hi" style="color:${tCol};">${d.hi}°</div>
      <div class="wx-fc-lo">${d.lo}°</div>
      ${d.chanceRain >= 20 ? `<div class="wx-fc-rain">💧${d.chanceRain}%</div>` : ""}
    </div>`;
      })
      .join("")
    : `<div style="color:var(--text-muted);font-family:var(--font-mono);font-size:12px;grid-column:1/-1;text-align:center;padding:20px;">Previsão indisponível.</div>`;

  const alerts = [];
  if (wx.temp > 35)
    alerts.push({
      i: "🔥",
      m: "Calor extremo — hidrate-se",
      c: "var(--danger)",
    });
  if (wx.temp < 5)
    alerts.push({ i: "🥶", m: "Temperatura muito baixa", c: "#7eb8ff" });
  if (wx.uv > 7)
    alerts.push({
      i: "☀️",
      m: "UV alto — protetor FPS 50+",
      c: "var(--accent2)",
    });
  if (wx.wind > 60) alerts.push({ i: "💨", m: "Vento forte", c: "#ffd700" });
  if (wx.humidity > 90)
    alerts.push({ i: "💧", m: "Alta umidade", c: "var(--accent)" });

  const alertsHTML = alerts.length
    ? alerts
      .map(
        (a) => `
      <div class="wx-chip" style="border-color:${a.c}55;background:${a.c}12;">
        <span>${a.i}</span>
        <span style="color:${a.c};">${a.m}</span>
      </div>`,
      )
      .join("")
    : `<div class="wx-chip" style="border-color:#00e67655;background:#00e67612;">
        <span>✅</span>
        <span style="color:#00e676;">Condições estáveis — sem alertas ativos</span>
       </div>`;

  const badge = getEl("wxSourceBadge");
  if (badge)
    badge.innerHTML = `<div class="wx-source"><div class="wx-source-dot"></div>${wx.source === "owm" ? "OWM" : "WTTR.IN"}</div>`;

  const bgMap = {
    clear: ["#0a0800", "#1a1000"],
    rain: ["#060810", "#03060d"],
    storm: ["#04050c", "#020305"],
    snow: ["#080c14", "#050810"],
    cloudy: ["#070a10", "#040608"],
    fog: ["#08090e", "#05060a"],
  };
  const conditionKey = wx.condition || "clear";
  const [gc1, gc2] = bgMap[conditionKey] || bgMap.clear;

  el.innerHTML = `
  <div class="wx-hero">
    <div class="wx-canvas-wrap" id="wxCanvasWrap" style="background: linear-gradient(to bottom, ${gc1}, ${gc2});">
        <canvas id="wxBgCanvas" style="position: absolute; width: 100%; height: 100%;"></canvas>
    </div>
    <div class="wx-hero-left">
      <div class="wx-hero-content">
        <div class="wx-city-label">${escHtml(wx.city)}${wx.country ? " · " + escHtml(wx.country) : ""}</div>
        <div class="wx-temp-display" style="color:${tCol};">${wx.temp}<sup>°C</sup></div>
        <div class="wx-desc">${escHtml(wx.desc)}</div>
        <div class="wx-feels">Sensação ${wx.feels}°C &nbsp;·&nbsp; ${wx.windDir} ${wx.wind} km/h</div>
      </div>
      <div class="wx-icon-mega">${wx.icon}</div>
    </div>
    <div class="wx-stats-panel">
      <div class="wx-stat"><div class="wx-stat-lbl">💧 UMIDADE</div><div class="wx-stat-val" style="color:var(--accent);">${wx.humidity}<span>%</span></div></div>
      <div class="wx-stat"><div class="wx-stat-lbl">💨 VENTO</div><div class="wx-stat-val" style="color:var(--accent2);">${wx.wind}<span> km/h</span></div>${wx.windDir ? `<div class="wx-stat-sub">${wx.windDir}</div>` : ""}</div>
      <div class="wx-stat"><div class="wx-stat-lbl">🌡️ PRESSÃO</div><div class="wx-stat-val" style="color:#ffd700;">${wx.pressure}<span> hPa</span></div></div>
      <div class="wx-stat"><div class="wx-stat-lbl">☀️ ÍNDICE UV</div><div class="wx-stat-val" style="color:${uvCol};">${wx.uv || "—"}</div><div class="wx-stat-sub">${uvLbl}</div></div>
      <div class="wx-stat"><div class="wx-stat-lbl">👁️ VISIBILIDADE</div><div class="wx-stat-val">${wx.vis}<span> km</span></div></div>
      <div class="wx-stat"><div class="wx-stat-lbl">☁️ NEBULOSIDADE</div><div class="wx-stat-val">${wx.cloud}<span>%</span></div></div>
    </div>
  </div>

  <div class="wx-section-label">PREVISÃO · PRÓXIMOS 6 DIAS</div>
  <div class="wx-forecast-grid">${forecastHTML}</div>
  <div class="wx-section-label">ALERTAS ATIVOS</div>
  <div class="wx-alerts">${alertsHTML}</div>`;

  startWeatherCanvas(conditionKey, wx.temp);
}
window.renderWeatherFull = renderWeatherFull;

function startWeatherCanvas(condition, temp) {
  if (window.wxAnimFrame) {
    cancelAnimationFrame(window.wxAnimFrame);
    window.wxAnimFrame = null;
  }

  const canvas = getEl("wxBgCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d", { alpha: true });
  canvas.width = canvas.offsetWidth || 700;
  canvas.height = canvas.offsetHeight || 260;
  const W = canvas.width,
    H = canvas.height;
  let particles = [];
  const tCol =
    temp > 32
      ? "#ff6600"
      : temp > 22
        ? "#ffb400"
        : temp > 10
          ? "#00c8ff"
          : "#88aaff";

  if (condition === "rain" || condition === "storm") {
    for (let i = 0; i < 60; i++)
      particles.push({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: -1.5,
        vy: 12 + Math.random() * 8,
        len: 14 + Math.random() * 10,
        alpha: 0.15 + Math.random() * 0.25,
      });
  } else if (condition === "snow") {
    for (let i = 0; i < 40; i++)
      particles.push({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: Math.sin(i) * 0.5,
        vy: 1 + Math.random() * 1.5,
        r: 1.5 + Math.random() * 2.5,
        alpha: 0.2 + Math.random() * 0.4,
        t: Math.random() * Math.PI * 2,
      });
  } else if (condition === "clear") {
    for (let i = 0; i < 20; i++) {
      const angle = ((Math.PI * 2) / 20) * i;
      particles.push({
        angle,
        speed: 0.003 + Math.random() * 0.005,
        len: 60 + Math.random() * 80,
        alpha: 0.04 + Math.random() * 0.06,
      });
    }
  } else if (condition === "cloudy" || condition === "fog") {
    for (let i = 0; i < 5; i++)
      particles.push({
        x: Math.random() * W,
        y: 20 + Math.random() * (H * 0.6),
        vx: 0.15 + Math.random() * 0.2,
        r: 60 + Math.random() * 80,
        alpha: 0.05 + Math.random() * 0.06,
      });
  }

  let frame = 0;

  const tick = () => {
    if (!document.getElementById("wxBgCanvas")) {
      window.wxAnimFrame = null;
      return;
    }
    frame++;
    ctx.clearRect(0, 0, W, H);

    if (condition === "rain" || condition === "storm") {
      ctx.strokeStyle = "rgba(180,220,255,.35)";
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      particles.forEach((p) => {
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x + p.vx * 1.5, p.y + p.len);
        p.x += p.vx;
        p.y += p.vy;
        if (p.y > H) {
          p.y = -p.len;
          p.x = Math.random() * W;
        }
      });
      ctx.stroke();
    } else if (condition === "snow") {
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      particles.forEach((p) => {
        ctx.moveTo(p.x, p.y);
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        p.t += 0.02;
        p.x += Math.sin(p.t) * 0.5 + p.vx;
        p.y += p.vy;
        if (p.y > H) {
          p.y = -5;
          p.x = Math.random() * W;
        }
      });
      ctx.fill();
    } else if (condition === "clear") {
      const cx = W * 0.75,
        cy = H * 0.25;
      const sr = ctx.createRadialGradient(cx, cy, 0, cx, cy, 120);
      sr.addColorStop(0, tCol + "28");
      sr.addColorStop(1, "transparent");
      ctx.fillStyle = sr;
      ctx.fillRect(0, 0, W, H);
      particles.forEach((p) => {
        p.angle += p.speed;
        ctx.globalAlpha =
          p.alpha * (0.7 + 0.3 * Math.sin(frame * 0.02 + p.angle));
        ctx.strokeStyle = tCol;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(p.angle) * 35, cy + Math.sin(p.angle) * 35);
        ctx.lineTo(
          cx + Math.cos(p.angle) * (35 + p.len),
          cy + Math.sin(p.angle) * (35 + p.len),
        );
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
    } else if (condition === "cloudy" || condition === "fog") {
      particles.forEach((p) => {
        ctx.globalAlpha =
          p.alpha * (0.8 + 0.2 * Math.sin(frame * 0.01 + p.x * 0.01));
        const cg = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
        cg.addColorStop(0, "rgba(180,200,220,.7)");
        cg.addColorStop(1, "transparent");
        ctx.fillStyle = cg;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
        p.x += p.vx;
        if (p.x - p.r > W) p.x = -p.r;
      });
      ctx.globalAlpha = 1;
    }
    window.wxAnimFrame = requestAnimationFrame(tick);
  };
  tick();
}

function renderSecaoConfig(wrap) {
  const el = wrap || getEl("section-config");
  if (!el) return;

  const apiFields = [
    { key: "gemini", label: "GEMINI API KEY", tip: "Google AI Studio" },
    { key: "qwen", label: "QWEN API KEY", tip: "Alibaba Cloud" },
    { key: "smartthings", label: "SMARTTHINGS TOKEN", tip: "SmartThings API" },
    {
      key: "smartthings_tv_id",
      label: "ID DA TV (SmartThings)",
      tip: "deviceId da TV",
    },
    { key: "spotify_id", label: "SPOTIFY CLIENT ID", tip: "Spotify Dashboard" },
    { key: "spotify_sec", label: "SPOTIFY SECRET", tip: "Spotify Dashboard" },
  ];

  el.innerHTML = `
  <div class="cfg-shell">
    <div class="cfg-topbar">
      <div>
        <div class="cfg-title">CONFIGURAÇÃO</div>
        <div class="cfg-sub">Chaves de API · Preferências · Sistema</div>
      </div>
      <div style="display:flex;gap:10px;">
        <button class="btn-save-field ${state.configEdit ? "saved" : ""}" onclick="toggleEditConfig()">
          ${state.configEdit ? "🔓 BLOQUEAR" : "🔒 EDITAR CHAVES"}
        </button>
        <button class="btn-save-field" onclick="salvarConfigAvancado()">💾 SALVAR TUDO</button>
      </div>
    </div>

    <div class="cfg-section">
      <div class="section-title">CHAVES DE API</div>
      <div class="cfg-api-grid">
        ${apiFields
      .map(
        (f) => `
        <div class="cfg-api-field">
          <div class="cfg-api-top">
            <div style="font-family:var(--font-mono);font-size:10px;letter-spacing:2px;color:var(--text-muted);">${f.label}</div>
            <div class="cfg-api-dot ${state.apis[f.key] ? "ok" : ""}" id="dot_${f.key}"></div>
          </div>
          <input class="field-input" id="api_${f.key}" type="password"
                 placeholder="${f.tip}"
                 value="${escHtml(state.apis[f.key] || "")}"
                 ${state.configEdit ? "" : "readonly"}
                 style="${state.configEdit ? "" : "opacity:.45;cursor:not-allowed;"}"
                 oninput="onApiInputAdv('${f.key}', this.value)">
        </div>`,
      )
      .join("")}
      </div>
    </div>

    <div class="cfg-section">
      <div class="section-title">PREFERÊNCIAS</div>
      <div style="display:flex;flex-direction:column;gap:12px;max-width:400px;">
        <div>
          <div style="font-family:var(--font-mono);font-size:10px;letter-spacing:2px;color:var(--text-muted);margin-bottom:6px;">NOME DO MESTRE</div>
          <div class="field-row-inline">
            <input class="field-input" id="cfg-nome-mestre"
                   value="${escHtml(state.apis.nome_mestre || "")}"
                   placeholder="David"
                   ${state.configEdit ? "" : "readonly"}
                   style="${state.configEdit ? "" : "opacity:.45;cursor:not-allowed;"}"
                   oninput="state.apis.nome_mestre=this.value">
            <button class="btn-save-field" onclick="salvarCampoAdv('nome_mestre','cfg-nome-mestre',this)">SALVAR</button>
          </div>
        </div>
        <div>
          <div style="font-family:var(--font-mono);font-size:10px;letter-spacing:2px;color:var(--text-muted);margin-bottom:6px;">CIDADE PADRÃO (CLIMA)</div>
          <div class="field-row-inline">
            <input class="field-input" id="cfg-cidade-padrao"
                   value="${escHtml(state.apis.cidade_padrao || "")}"
                   placeholder="Ex: São Paulo"
                   ${state.configEdit ? "" : "readonly"}
                   style="${state.configEdit ? "" : "opacity:.45;cursor:not-allowed;"}"
                   oninput="state.apis.cidade_padrao=this.value;state.weather.city=this.value;">
            <button class="btn-save-field" onclick="salvarCampoAdv('cidade_padrao','cfg-cidade-padrao',this)">SALVAR</button>
          </div>
        </div>
      </div>
    </div>

    <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);letter-spacing:1px;
         padding:12px 16px;background:var(--panel);border:1px solid var(--border);border-radius:4px;margin-top:4px;">
      Configurações persistidas em <span style="color:var(--accent);">api/config_core.json</span>
    </div>
  </div>`;
}

function toggleEditConfig() {
  state.configEdit = !state.configEdit;
  if (currentSection === "config") renderSecaoConfig();
  showToast(
    state.configEdit ? "🔓 EDIÇÃO LIBERADA" : "🔒 CONFIGURAÇÕES BLOQUEADAS",
  );
}
window.toggleEditConfig = toggleEditConfig;

function onApiInputAdv(key, val) {
  state.apis[key] = val;
  const dot = getEl(`dot_${key}`);
  if (dot) dot.className = "cfg-api-dot " + (val ? "ok" : "");
}
window.onApiInputAdv = onApiInputAdv;

function salvarCampoAdv(chave, inputId, btn) {
  if (!jarvis) {
    showToast("BRIDGE NÃO CONECTADA");
    return;
  }
  const val = getEl(inputId)?.value || "";
  jarvis.salvar_configuracao(chave, val);
  if (chave === "cidade_padrao") {
    state.weather.city = val;
    state.apis.cidade_padrao = val;
  }
  btn.textContent = "✓";
  setTimeout(() => {
    btn.textContent = "SALVAR";
  }, 1600);
  showToast("SALVO: " + chave.toUpperCase());
}
window.salvarCampoAdv = salvarCampoAdv;

function salvarConfigAvancado() {
  if (!jarvis) {
    showToast("BRIDGE NÃO CONECTADA", "err");
    return;
  }
  const keys = [
    "gemini",
    "qwen",
    "smartthings",
    "smartthings_tv_id",
    "spotify_id",
    "spotify_sec",
    "nome_mestre",
    "cidade_padrao",
  ];
  let saved = 0;
  keys.forEach((k) => {
    if (state.apis[k] !== undefined) {
      jarvis.salvar_configuracao(k, state.apis[k]);
      saved++;
    }
  });
  showToast(`✓ ${saved} CONFIGURAÇÕES SALVAS`);
  if (state.configEdit) toggleEditConfig();
}
window.salvarConfigAvancado = salvarConfigAvancado;

function renderSecaoTemas() {
  const wrap = getEl("section-temas");
  if (!wrap) return;

  const ids = Object.keys(state.themes);
  wrap.innerHTML = `
  <div class="cfg-shell">
    <div class="cfg-topbar">
      <div>
        <div class="cfg-title">PROTOCOLO VISUAL</div>
        <div class="cfg-sub">Selecione o esquema de cores da interface</div>
      </div>
    </div>

    ${ids.length === 0
      ? `<div style="text-align:center;padding:80px;color:var(--text-muted);font-family:var(--font-mono);font-size:13px;letter-spacing:2px;">
           Conecte o sistema para carregar os temas disponíveis.
         </div>`
      : `<div class="themes-grid">
          ${ids
        .map((id) => {
          const t = state.themes[id];
          const a1 = t.accent || "#00c8ff";
          const a2 = t.secondary || "#00ff9d";
          const a3 = t.danger || "#ff2255";
          const bg =
            t.bg_grad ||
            `linear-gradient(135deg,${a1}33 0%,${a2}1f 55%,${a3}24 100%)`;
          const active = state.theme === id;
          return `
            <div class="theme-card ${active ? "active-theme" : ""}"
                 style="border-color:${active ? a1 : "var(--border)"};"
                 onclick="aplicarTema('${id}')">
              <div class="theme-preview">
                <div class="theme-swatch" style="background:${bg};flex:3;"></div>
                <div class="theme-swatch" style="background:${a1};"></div>
                <div class="theme-swatch" style="background:${a2};"></div>
                <div class="theme-swatch" style="background:${a3};"></div>
              </div>
              <div class="theme-name" style="color:${a1};">${id}</div>
              <button class="theme-apply-btn"
                      style="border-color:${a1};color:${a1};background:${active ? a1 + "1a" : "transparent"};">
                ${active ? "✓ ATIVO" : "APLICAR"}
              </button>
            </div>`;
        })
        .join("")}
         </div>`
    }

    <div style="margin-top:16px;padding:12px 16px;background:var(--panel);border:1px solid var(--border);border-radius:4px;
         font-family:var(--font-mono);font-size:11px;color:var(--text-muted);letter-spacing:1px;">
      Tema ativo persistido em <span style="color:var(--accent);">api/config_core.json</span>
      · restaurado automaticamente no próximo boot.
    </div>
  </div>`;
}

function aplicarTema(id) {
  if (!state.themes[id]) return;
  state.theme = id;
  applyTheme(id);
  if (jarvis) jarvis.salvar_configuracao("tema_ativo", id);
  if (currentSection === "temas") renderSecaoTemas();
  showToast("TEMA " + id + " ATIVADO");
}
window.aplicarTema = aplicarTema;

function applyTheme(id) {
  const t = state.themes[id];
  if (!t) return;
  const r = document.documentElement;
  r.style.setProperty("--accent", t.accent || "#ff9500");
  r.style.setProperty("--accent2", t.secondary || "#ff6600");
  r.style.setProperty("--bg", t.bg || "#050608");
  if (t.bg_grad) r.style.setProperty("--bg-grad", t.bg_grad);
  else r.style.removeProperty("--bg-grad");
  r.style.setProperty("--panel", t.card || "#0d0e12");
  r.style.setProperty("--border", t.border || "rgba(255,149,0,0.18)");
  r.style.setProperty("--border-hi", t.border || "rgba(255,149,0,0.45)");
  r.style.setProperty("--text", t.text_pri || "#e8dfc8");
  r.style.setProperty("--text-dim", t.text_sec || "rgba(232,223,200,0.5)");
  r.style.setProperty("--text-muted", t.text_sec || "rgba(232,223,200,0.28)");
  r.style.setProperty("--danger", t.danger || "#ff3b30");
  if (t.surface) r.style.setProperty("--bg2", t.surface);
}
window.applyTheme = applyTheme;

function analisarTela() {
  if (!jarvis) return;
  getEl("vision-status").textContent = "Capturando tela...";
  jarvis.solicitar_analise_visual();
}
window.analisarTela = analisarTela;

function analisarTelaCustom() {
  if (!jarvis) return;
  const prompt = getEl("vision-prompt").value.trim();
  getEl("vision-status").textContent = "Analisando...";
  if (prompt) jarvis.solicitar_analise_visual_com_prompt(prompt);
  else jarvis.solicitar_analise_visual();
}
window.analisarTelaCustom = analisarTelaCustom;

function adicionarEventoMonitor(ev) {
  const el = getEl("monitor-events");
  if (!el) return;
  const empty = el.querySelector(".empty-state");
  if (empty) empty.remove();
  const tipo = ev.ok
    ? "ok"
    : ev.tipo === "erro" || ev.tipo === "crash"
      ? "error"
      : "warn";
  const div = document.createElement("div");
  div.className = `monitor-event ${tipo}`;
  div.innerHTML = `<span class="monitor-event-ts">${agora()}</span>${escHtml(ev.resumo || ev.tipo || "Evento")}`;
  el.insertBefore(div, el.firstChild);
  while (el.children.length > 30) el.removeChild(el.lastChild);
}

function atualizarMetrica(tipo, val) {
  const v = parseFloat(val) || 0;
  const danger = v > 85;
  if (tipo === "cpu") {
    const elCpuVal = getEl("cpu-val");
    if (elCpuVal) elCpuVal.textContent = Math.round(v);
    const sb = getEl("bar-cpu");
    if (sb) {
      sb.style.width = v + "%";
      sb.classList.toggle("danger", danger);
    }
    const sc = getEl("s-cpu");
    if (sc) sc.textContent = Math.round(v);
    const st = getEl("s-cpu-tile");
    if (st) st.textContent = Math.round(v);
    const bt = getEl("bar-cpu-tile");
    if (bt) {
      bt.style.width = v + "%";
      bt.classList.toggle("danger", danger);
    }
  } else {
    const elRamVal = getEl("ram-val");
    if (elRamVal) elRamVal.textContent = Math.round(v);
    const sb = getEl("bar-ram");
    if (sb) {
      sb.style.width = v + "%";
      sb.classList.toggle("danger", danger);
    }
    const sr = getEl("s-ram");
    if (sr) sr.textContent = Math.round(v);
    const st = getEl("s-ram-tile");
    if (st) st.textContent = Math.round(v);
    const bt = getEl("bar-ram-tile");
    if (bt) {
      bt.style.width = v + "%";
      bt.classList.toggle("danger", danger);
    }
  }
}

function enviarComando(cmd) {
  if (!jarvis) return;
  jarvis.executar_comando(cmd);
  adicionarMensagem("user", cmd);
  switchTab("chat");
  showToast("EXECUTANDO: " + cmd.toUpperCase());
}
window.enviarComando = enviarComando;

function ocultarPainel() {
  if (jarvis) jarvis.ocultar_painel();
}
window.ocultarPainel = ocultarPainel;

function agora() {
  return new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function setVal(id, val) {
  const el = getEl(id);
  if (!el) return;
  if (el.tagName === "SELECT") {
    for (let o of el.options) {
      if (o.value === String(val)) {
        o.selected = true;
        break;
      }
    }
  } else {
    el.value = val;
  }
}

function escHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

let toastTimer;
function showToast(msg) {
  const t = getEl("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}
window.toast = showToast;

setInterval(atualizarStatusIA, 15000);
