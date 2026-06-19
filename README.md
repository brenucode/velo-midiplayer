<p align="center">
  <img src="assets/velo-banner.svg" alt="Velo" width="100%" />
</p>

<p align="center">
  <strong>Um player de MIDI clean — com estúdio de treino e modo palco.</strong><br/>
  Toca MIDI convertendo em teclas (pra tocar em pianos virtuais de jogos) ou em saída MIDI.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/plataforma-Windows%2010%2F11-1c1c23?style=flat-square" />
  <img src="https://img.shields.io/badge/versão-v1.0-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/licença-GPL%20v3-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/feito%20por-brenu-1c1c23?style=flat-square" />
</p>

---

O **Velo** nasceu de uma vontade simples: tocar MIDI numa interface que não tivesse cara de software de 2009. Player limpo, biblioteca de músicas online, um modo de treino que parece um joguinho, e um modo palco pra deixar bonito na stream. Sem firula, sem instalação chata — abre e funciona.

<p align="center">
  <em>📸 (coloque aqui um print do app — ex.: <code>docs/screenshot.png</code>)</em>
</p>

## ✨ O que ele faz

- 🎹 **Player** — toca MIDI via **teclado (QWERTY)** ou **saída MIDI**. Fila de músicas, controle de velocidade, anterior/próxima, e **atalhos globais** que funcionam até com o app em segundo plano.
- 🎯 **Treino** — três modos num teclado de 61 teclas que mostra qual tecla apertar:
  - **Step** — aprende nota por nota, no seu ritmo. Errou? Trava até você acertar.
  - **Rhythm** — vira jogo de ritmo: as notas caem no tempo da música, com **Perfect / Good / Miss**, combo, multiplicador e barra de vida.
  - **Free play** — piano livre (teclado ou mouse), com **rastros subindo** a cada nota e **preview** da música tocando sozinha.
  - **Treinador de trecho** — escolhe o pedaço difícil e treina em **câmera lenta que acelera** conforme você acerta.
- 🌐 **MIDI Hub** — baixa músicas direto do **BitMidi** (milhares de arquivos), busca e paginação.
- ▦ **Modo Palco** — as notas caem num piano em **tela cheia**, sincronizadas com o que toca. Perfeito pra deixar na tela no Discord/stream.
- 🥁 **Drums** e ⌨️ **MIDI → Teclas** — controlador MIDI vira teclado em tempo real.
- 🔊 **Som de verdade** — vários modelos de **piano** (Grand, Bright, Electric…) e som de **teclado mecânico Cherry MX**.
- 🏆 **Recordes** por música · 🖥️ layout **responsivo** + **fullscreen (F11)**.

## ⬇️ Baixar (pronto pra usar)

> Não precisa de Python nem instalar nada.

1. Vai em **[Releases](../../releases)** e baixa o `Velo-win.zip`.
2. Extrai a pasta onde quiser.
3. Abre o **`Velo.exe`**.

Requer **Windows 10/11** com o **WebView2 Runtime** (já vem instalado no Windows atualizado; se faltar, o Windows Update resolve ou baixa de graça na Microsoft).

## ⌨️ Atalhos globais

| Tecla | Ação |
|:-----:|------|
| `F1`  | Play / Pause |
| `F2`  | Pause |
| `F3`  | Stop |
| `F4`  | Aumentar velocidade |
| `F5`  | Diminuir velocidade |
| `F6`  | Música anterior |
| `F7`  | Próxima música |

Dá pra trocar qualquer atalho em **Settings**. Eles funcionam mesmo com o Velo minimizado — ideal pra controlar enquanto você está num jogo.

## 🧭 Como usar

### 1. Tocar uma música
1. Aba **Player** → **Open** (ou arraste um `.mid` pra janela).
2. **Play** (ou `F1`). O Velo "digita" a música nas teclas do seu piano virtual.
3. Quer tocar num jogo (Roblox, etc.)? Deixa o jogo em foco e use os atalhos — as teclas vão pra ele.

> **QWERTY x MIDI Output:** no topo do Player você escolhe. *QWERTY* simula o teclado (pra pianos de jogos). *MIDI Output* manda pra um instrumento/DAW via porta MIDI.

### 2. Baixar músicas (MIDI Hub)
1. Aba **MIDI Hub** → busca pelo nome.
2. Clica no ↓ de uma música — ela baixa e já entra na sua fila.

### 3. Treinar
1. Aba **Practice** → escolhe o modo (**Step / Rhythm / Free play**) e a música.
2. O teclado na tela acende as teclas certas (sustenidos = **Shift**).
   - **Step:** aperta na sequência, sem pressa.
   - **Rhythm:** acerta no tempo em que a nota chega na linha.
   - **Free play:** toca livre; escolhe uma música e dá **Play (preview)** pra assistir tocando sozinha.
3. **Treinador de trecho:** liga o *Section trainer* e arrasta os limites pra treinar só um pedaço, devagar.

### 4. Modo Palco (visualizer)
No **Player**, clique em **Stage** (ou `F11` pra tela cheia). Dá play numa música e as notas caem no piano, sincronizadas — bonito pra stream.

### 5. 🎙️ Soar como se estivesse tocando ao vivo (Discord / stream)
A ideia: rotear o som do piano do Velo pro seu "microfone" virtual.

1. Instale o **[VB-CABLE](https://vb-audio.com/Cable/)** (cabo de áudio virtual, grátis).
2. No Windows, em **Configurações → Sistema → Som → Mixer de volume**, mande a saída do **Velo** para **`CABLE Input`**.
3. No **Discord / OBS**, escolha o microfone **`CABLE Output`**.
4. No Velo, em **Settings → Sound**, ligue o som (piano ou teclado) e dê o play.
5. Pronto — quem te ouve recebe o piano como se fosse você tocando.

> Quer **falar e tocar ao mesmo tempo**? Use o **VoiceMeeter** pra misturar seu microfone real + o áudio do Velo num só canal.

### 6. Drums e MIDI → Teclas
- **Drums:** mesma lógica do Player, com mapa de bateria.
- **MIDI → Teclas:** conecte um controlador MIDI e toque — o Velo converte pra teclas em tempo real.

## 🛠️ Rodar do código-fonte

Pré-requisitos: **Python 3.12** (Windows) e o **WebView2 Runtime**.

```bash
python -m venv venv-win
venv-win\Scripts\activate
pip install -r requirements.txt
python velo_app.py
```

Pra gerar o `.exe` (build com PyInstaller, sem cara de falso-positivo):

```bash
scripts\build-velo-win.bat
```

O app sai em `dist\Velo\Velo.exe`.

## 🙏 Créditos & Licença

**Velo** — criado por **brenu** · [github.com/brenucode](https://github.com/brenucode)
Copyright © 2026 brenu.

Distribuído sob a **GNU General Public License v3.0** (veja [LICENSE](LICENSE)).

Construído sobre o motor de reprodução do **[nanoMIDIPlayer](https://github.com/NotHammer043/nanoMIDIPlayer)** (NotHammer043), também licenciado em GPLv3 — obrigado pela base.

Sons: pianos **MusyngKite** ([midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts)) e teclado **Cherry MX** ([Mechvibes](https://github.com/hainguyents13/mechvibes)).

<p align="center"><sub>feito no tempo livre — porque nem todo projeto precisa de justificativa.</sub></p>
