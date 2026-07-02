# 🤖 **J.A.R.V.I.S — Mark XXVIII**

> Assistente de voz com IA, automação residencial, monitoramento de sistema e segurança de rede. Tudo controlado por comando de voz, painel web ou Telegram.

---

## 📢 **COMANDOS DE VOZ**

**Wake word:** `"Jarvis"` — detectado mesmo em meio a frases, com correção fuzzy de erros de STT.

### 🖥️ **Controle do PC**
| Comando | Ação |
|---|---|
| `"Jarvis, abrir YouTube"` | Abre qualquer aplicativo (50+ atalhos) |
| `"Jarvis, fechar"` | Fecha janela ativa (Alt+F4) |
| `"Jarvis, bloquear"` | Trava a estação de trabalho |
| `"Jarvis, minimizar"` | Mostra a área de trabalho (Win+D) |
| `"Jarvis, mutar"` | Silencia o sistema |
| `"Jarvis, volume 50"` | Ajusta volume (0-100) |
| `"Jarvis, print"` | Captura screenshot de todas as telas |
| `"Jarvis, limpar lixeira"` | Esvazia a lixeira |
| `"Jarvis, digitar Hello World"` | Digita texto automaticamente |

### 🎵 **Spotify**
| Comando | Ação |
|---|---|
| `"Jarvis, tocar [música]"` | Busca e toca uma música |
| `"Jarvis, playlist [nome]"` | Toca uma playlist |
| `"Jarvis, favoritas"` | Toca músicas curtidas |
| `"Jarvis, pausar / continuar"` | Pausa/retoma |
| `"Jarvis, próxima / anterior"` | Próxima/anterior faixa |

### 📺 **SmartThings (Samsung TV)**
| Comando | Ação |
|---|---|
| `"Jarvis, ligar TV"` | Liga a TV |
| `"Jarvis, desligar TV"` | Desliga a TV |
| `"Jarvis, YouTube na TV"` | Abre YouTube na TV |
| `"Jarvis, volume 30 na TV"` | Ajusta volume da TV |

### 🌤️ **Clima & Notícias**
| Comando | Ação |
|---|---|
| `"Jarvis, como está o tempo?"` | Previsão do tempo (detecta cidade automaticamente) |
| `"Jarvis, vai chover amanhã?"` | Previsão de chuva |
| `"Jarvis, notícias"` | Últimas manchetes (Folha, G1, BBC) |
| `"Jarvis, briefing"` | Briefing completo: clima + notícias + agenda + e-mails |

### ⏰ **Produtividade**
| Comando | Ação |
|---|---|
| `"Jarvis, acorde-me às 7:00"` | Cria alarme |
| `"Jarvis, parar alarme"` | Para o alarme |
| `"Jarvis, focar 25 minutos"` | Inicia Pomodoro (configurável) |
| `"Jarvis, pausa 5 minutos"` | Inicia pausa do Pomodoro |
| `"Jarvis, status do foco"` | Tempo restante do Pomodoro |
| `"Jarvis, quais eventos hoje?"` | Eventos da agenda |
| `"Jarvis, adicionar evento"` | Cria evento no calendário |
| `"Jarvis, ver e-mails"` | Checa e-mails não lidos (IMAP) |
| `"Jarvis, pesquisar sobre [assunto]"` | Pesquisa Google no navegador |

### 🛠️ **Comandos Customizados (& Seus Próprios Comandos)**
| Comando | Ação |
|---|---|
| `"Jarvis, listar comandos"` | Lista comandos customizados |
| `"Jarvis, adicionar comando [nome] tipo [app/url/fala]"` | Cria comando próprio |
| `"Jarvis, remover comando [nome]"` | Remove comando customizado |

### 💻 **Terminal & Código**
| Comando | Ação |
|---|---|
| `"Jarvis, terminal: dir"` | Executa comando no terminal (com sandbox de segurança) |
| `"Jarvis, crie um script Python que..."` | Gera e executa código automaticamente |

---

## 🧠 **MOTORES DE IA**

| Provedor | Como ativar |
|---|---|
| **LM Studio** (local) | Padrão — modelos rodando em `localhost:1234` |
| **Google Gemini** | Configurar chave no painel |
| **OpenRouter** | Configurar chave no painel (ex: Qwen 2.5 VL 72B) |

O roteador de modelo escolhe automaticamente entre **phi3** (rápido), **llama3** (médio) e **qwen** (pesado/visão) conforme a complexidade do comando.

---

## 📊 **MONITORAMENTO DE SISTEMA (Sentinela)**

Ativo **24/7** em segundo plano — verifica a cada 10 segundos:

- 🌡️ **Temperatura da CPU** — alerta falado se >82°C
- 🔋 **Bateria** — alerta se <20%
- 💾 **Disco** — alerta se >90%
- 🖥️ **CPU/RAM** — alerta se >90%
- 🌐 **Internet** — detecta queda de conexão
- 🎮 **GPU** — uso, temperatura e memória

Tudo registrado em banco SQLite com histórico de métricas.

---

## 🔒 **SEGURANÇA DE REDE**

- **Escaneamento ARP** — descobre dispositivos na rede local
- **Detecção de trackers** — identifica 24+ domínios de rastreamento (Google Analytics, Facebook, etc.)
- **Monitor de conexões** — portas suspeitas (22, 23, 3389, 5900, etc.)
- **Firewall** — verifica status das regras do Windows Firewall

---

## 👁️ **HUD OVERLAY (Tela Transparente)**

Interface gráfica estilo **Homem de Ferro** com:

- 5 temas animados: 🟠 Laranja 🔵 Azul 🟣 Roxo 🟢 Verde 🔴 Vermelho
- Núcleo pulsante com anéis concêntricos
- Tentáculos animados com curvas Bezier
- Sistema de partículas (3 camadas)
- Arco de varredura rotativo (estilo Pac-Man)
- Ícone na bandeja do sistema com menu de contexto
- Botões: microfone (mute), painel, desligar

---

## 🌐 **PAINEL DE CONTROLE WEB**

8 páginas no navegador integrado:

| Página | Funcionalidades |
|---|---|
| **🏠 Início** | Métricas em tempo real (CPU, RAM, Disco, Bateria, Temp, GPU), logs, status do Sentinela |
| **💬 Chat** | Conversa direta com a IA |
| **⏰ Alarmes** | Criar/gerenciar alarmes com repetição diária |
| **🌤️ Clima** | Previsão do tempo por cidade |
| **📅 Calendário** | Eventos do dia, adicionar/remover |
| **📧 E-mail** | Configurar IMAP, ler e-mails |
| **⚙️ Config** | Todas as configurações (voz, API keys, Spotify, SmartThings, Telegram, Whisper, etc.) |
| **📚 Biblioteca** | Catálogo completo de comandos com busca e execução com 1 clique |

---

## 📱 **TELEGRAM BOT**

Comandos disponíveis no Telegram:

```
/jarvis [comando]  — Executa qualquer comando de voz
/status            — Status do sistema
/clima [cidade]    — Previsão do tempo
/alarme HH:MM      — Cria alarme
/stop              — Para a fala do Jarvis
/ajuda             — Lista de comandos
```

🔐 **Autenticação por token** — apenas usuários autorizados podem usar.

---

## 👏 **DETECÇÃO DE PALMAS**

Dê **2 palmas** e o Jarvis ativa — sem precisar falar "Jarvis".  
Análise FFT na faixa de 800–4000Hz com debounce de 1s.

---

## 🛠️ **16 FERRAMENTAS DE IA (Function Calling)**

O cérebro do Jarvis pode usar ferramentas automaticamente:

1. **Abrir aplicativos** — qualquer app instalado
2. **Controle do PC** — fechar, minimizar, print, bloquear, volume
3. **Terminal** — executar comandos (com auditoria)
4. **Pesquisa web** — buscar e resumir informações
5. **Navegador** — abrir URLs ou pesquisar
6. **YouTube** — buscar e abrir vídeos
7. **Spotify** — controle completo de reprodução
8. **Clima** — previsão por cidade
9. **Alarmes** — gerenciar lembretes
10. **Casa inteligente** — controle de dispositivos SmartThings
11. **Arquivos** — listar, criar, ler, deletar, info de disco
12. **Planos** — criar planos estruturados com IA
13. **Código** — gerar, depurar e executar código
14. **Trocar modo IA** — alternar entre provedores
15. **Automação visual** — GUI automation (em desenvolvimento)
16. **Tradução de áudio** — escutar e traduzir áudio ambiente

---

## ⚙️ **TECNOLOGIAS**

| Componente | Tecnologia |
|---|---|
| TTS (fala) | Microsoft Edge TTS (`edge-tts`) |
| STT (escuta) | `faster-whisper` (modelos tiny → large) |
| Wake word | Detecção própria com fuzzy matching + 28 correções STT |
| Interface desktop | PyQt6 + QWebEngine |
| Overlay animado | PyQt6 com pintura personalizada (QPainter) |
| Painel web | HTML + CSS + JS + QWebChannel |
| IA Local | LM Studio (API compatível com OpenAI) |
| IA Nuvem | Google Gemini ou OpenRouter |
| Banco de dados | SQLite (cache, alarmes, métricas, auditoria) |
| Áudio | sounddevice + pygame |
| Automação | pyautogui + psutil + wmi |
