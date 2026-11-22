> [!NOTE]
> **AI-Generated Content**
>
> **Nota de Transparência:** A estrutura e o código deste repositório foram gerados com o auxílio de Inteligência Artificial (ex: ChatGPT, Claude, Copilot) e revisados manualmente.

# Anki-Audio-Generator

Generate speech audio automatically for your Anki cards using Edge-TTS + AnkiConnect.

Gera áudio de voz (Edge-TTS) para os seus cards do Anki e o insere nos campos certos pelo AnkiConnect. Entende fórmulas MathJax/LaTeX (lê "limite de f de x quando x tende a zero" em vez do código) e transforma o trecho escondido de um Cloze em uma pausa no áudio da pergunta.

---

# 🤖 Aviso

Este projeto foi desenvolvido com o auxílio de Inteligência Artificial.

A implementação do código, a estrutura do projeto e parte da documentação foram geradas e refinadas utilizando ferramentas de IA sob orientação do autor.

O repositório é disponibilizado com o objetivo de compartilhar uma solução útil para a comunidade e servir como material de estudo. Todo o código deve ser revisado e testado antes de ser utilizado em ambientes de produção.

A transparência sobre o uso de IA faz parte da filosofia deste projeto.

---

# 📦 Requisitos

- Python 3.10+
- Anki (aberto durante a execução)
- Add-on AnkiConnect
- **ffmpeg** instalado no sistema (usado pelo `pydub` nos cards Cloze)
- Bibliotecas Python: `requests`, `edge-tts`, `pydub` (já listadas em `requirements.txt`)
- Conexão com a internet (o Edge-TTS gera a voz online)

---

# 🔧 Instalação

```bash
git clone https://github.com/danielDL1001/AI_Anki_Audio_Generator.git

cd AI_Anki_Audio_Generator

python -m venv .venv

source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Instalar o ffmpeg

```text
Linux (Debian/Ubuntu):  sudo apt install ffmpeg
macOS (Homebrew):       brew install ffmpeg
Windows:                winget install Gyan.FFmpeg   (ou baixe em ffmpeg.org e coloque no PATH)
```

Teste com `ffmpeg -version`.

---

# 🔌 Instalar o AnkiConnect

Abra o Anki.

Depois vá em:

```text
Ferramentas → Add-ons → Obter Add-ons...
```

Cole este código:

```text
2055492159
```

Reinicie o Anki.

---

# ⚠ IMPORTANTE

O script NÃO gera áudio para todos os cards.

Ele gera áudio SOMENTE para notas que possuem a tag:

```text
audio
```

---

# 🏷 Como criar a tag `audio`

## 1. Abrir o navegador do Anki

Clique em **Procurar** ou pressione `B`.

## 2. Selecionar os cards

Selecione um card, vários cards ou um deck inteiro.

## 3. Adicionar a tag

Na barra superior: `Notas → Adicionar etiquetas...` (ou `Ctrl + Shift + A`).

Digite `audio` e clique em **OK**.

## 4. Conferir

No navegador do Anki, pesquise:

```text
tag:audio
```

Se os cards aparecerem, está funcionando.

---

# 🧠 Tipos de nota e campos de áudio

O script funciona com **tipos de nota** (note types) e, para cada um, uma lista de campos: de qual campo vem o **texto** e em qual campo o **áudio** é gravado.

Na primeira execução ele já conhece dois tipos de nota:

| Tipo de nota  | Campo de texto | Campo de áudio (destino) | O que é narrado                                      |
| ------------- | -------------- | ------------------------ | ---------------------------------------------------- |
| `Basic_audio` | `Front`        | `FrontAudio`             | O texto do campo                                     |
| `Basic_audio` | `Back`         | `BackAudio`              | O texto do campo                                     |
| `Basic_audio` | `Example`      | `ExampleAudio`           | O texto do campo                                     |
| `Cloze_audio` | `Text`         | `TextAudio`              | A pergunta; o trecho `{{c1::...}}` vira uma **pausa** |
| `Cloze_audio` | `Text`         | `ExtraAudio`             | O conteúdo escondido no Cloze + o campo `Extra`      |

Esses tipos de nota precisam existir no Anki com esses nomes. **Você não precisa criar os campos de áudio à mão**: o script cria os campos de destino automaticamente quando eles não existem.

Para usar outros tipos de nota ou outros nomes de campo, use o menu de configuração (veja [Executar](#-executar)). A configuração fica salva em `~/anki_tts_config.json`.

---

# 🎴 Mostrar os áudios no card

O áudio NÃO toca se o template do card não tiver o campo de áudio. Em **Editar → Cards...**, adicione os campos nos templates.

## `Basic_audio` (exemplo)

**Frente**

```html
{{Front}}

{{FrontAudio}}
```

**Verso**

```html
{{FrontSide}}

<hr id=answer>

{{Back}}

{{BackAudio}}

{{Example}}

{{ExampleAudio}}
```

O `{{FrontSide}}` mostra o conteúdo da frente no verso sem tocar de novo o áudio da frente. Assim, o áudio da frente toca só na frente e o do verso só no verso.

## `Cloze_audio` (exemplo)

**Frente**

```html
{{cloze:Text}}

{{TextAudio}}
```

**Verso**

```html
{{cloze:Text}}

<br>

{{Extra}}

{{ExtraAudio}}
```

---

# ▶ Executar

Abra o Anki primeiro. Depois rode:

```bash
python main.py
```

O menu inicial oferece:

```text
1 - Gerar áudios
2 - Configurar tipos de nota / campos (adicionar, editar ou remover)
```

## Gerar áudios

1. O script procura as notas com a tag `audio`.
2. Para cada tipo de nota encontrado, mostra os campos de áudio configurados e você escolhe quais gerar (números separados por vírgula, ou `todos`).
3. Se algum campo de áudio já estiver preenchido, ele pergunta:
   - **1 - Ignorar áudios existentes**: pula os campos que já têm `[sound:...]`.
   - **2 - Refazer todos os áudios**: gera de novo e sobrescreve.
4. Cada áudio é enviado ao Anki pelo AnkiConnect e o campo recebe `[sound:arquivo.mp3]`.

Os arquivos são nomeados `<id da nota>_<campo>.mp3`, por exemplo `123456_frontaudio.mp3`.

## Configurar tipos de nota / campos

O menu `2` lista os tipos de nota do seu Anki e mostra os campos reais como lista numerada. Você escolhe o campo de texto, informa o campo de destino do áudio (se ele não existir, o script cria) e indica se o texto usa Cloze. Nada precisa ser editado no código.

---

# 🧮 Fórmulas MathJax/LaTeX

Antes de enviar o texto ao Edge-TTS, fórmulas como `\( ... \)` e `\[ ... \]` (e as variantes antigas `[$] ... [/$]`) viram uma frase em português: limites, frações, raízes, potências, integrais, somatórios, derivadas e os símbolos mais comuns.

A conversão só afeta o texto enviado à voz. O campo original do card **não é alterado**, e a fórmula continua renderizada normalmente.

Para rodar os testes da conversão:

```bash
python main.py --testar-latex
```

A conversão cobre os casos comuns (foco em Cálculo I). Expressões muito incomuns podem não virar uma frase perfeita.

---

# 🎤 Vozes

A voz padrão é `pt-BR-FranciscaNeural`. Para trocar sem editar o código, use a variável de ambiente `VOICE`:

```bash
# Linux / macOS
VOICE=en-US-JennyNeural python main.py

# Windows (PowerShell)
$env:VOICE = "en-US-JennyNeural"; python main.py

# Windows (cmd)
set VOICE=en-US-JennyNeural && python main.py
```

O Edge-TTS possui várias vozes naturais em diferentes idiomas.

## 🇧🇷 Português (Brasil)

- Femininas: `pt-BR-FranciscaNeural`, `pt-BR-BrendaNeural`
- Masculinas: `pt-BR-AntonioNeural`, `pt-BR-DonatoNeural`

## 🇺🇸 English

- Femininas: `en-US-JennyNeural`, `en-US-AriaNeural`, `en-US-AnaNeural`, `en-GB-SoniaNeural`
- Masculinas: `en-US-GuyNeural`, `en-US-DavisNeural`, `en-GB-RyanNeural`

## 🇯🇵 Japonês

- Femininas: `ja-JP-NanamiNeural`, `ja-JP-AoiNeural`
- Masculinas: `ja-JP-KeitaNeural`, `ja-JP-DaichiNeural`

## 🇪🇸 Espanhol

- Femininas: `es-ES-ElviraNeural`, `es-MX-DaliaNeural`
- Masculinas: `es-ES-AlvaroNeural`, `es-MX-JorgeNeural`

## 🧪 Listar todas as vozes

```bash
edge-tts --list-voices
```

Mostra idioma, nome, país e gênero de cada voz.

## 💡 Recomendações

| Uso                | Voz                     |
| ------------------ | ----------------------- |
| Cards em português | `pt-BR-FranciscaNeural` |
| Inglês             | `en-US-JennyNeural`     |
| Japonês            | `ja-JP-NanamiNeural`    |
| Espanhol           | `es-ES-ElviraNeural`    |

---

# 🐳 Docker

Também dá para rodar dentro de um container (a imagem já inclui o ffmpeg). O Anki continua rodando **no seu computador**, e o container conversa com o AnkiConnect pela rede.

```bash
docker compose build

docker compose run --rm anki-audio-generator
```

Use `run` (e não `up`), porque o script é interativo e precisa do seu teclado.

O `compose.yaml` já define:

| Variável         | Valor padrão                         | Função                                       |
| ---------------- | ------------------------------------ | -------------------------------------------- |
| `ANKICONNECT_URL` | `http://host.docker.internal:8765`   | Onde está o AnkiConnect (no seu computador)  |
| `CONFIG_FILE`    | `/data/anki_tts_config.json`         | Config salva num volume, não se perde ao sair |
| `VOICE`          | `pt-BR-FranciscaNeural`              | Voz do Edge-TTS                              |

## Liberar o acesso do container ao AnkiConnect

Por padrão, o AnkiConnect só aceita conexões do próprio computador (`127.0.0.1`).

- **Windows / macOS (Docker Desktop):** normalmente funciona sem mudar nada.
- **Linux:** em `Ferramentas → Add-ons → AnkiConnect → Config`, troque `webBindAddress` para `0.0.0.0` (ou para o IP da ponte do Docker, geralmente `172.17.0.1`) e reinicie o Anki.

> ⚠ O AnkiConnect não tem senha por padrão. Com `0.0.0.0`, qualquer dispositivo da sua rede local consegue acessá-lo. Prefira o IP da ponte do Docker ou bloqueie a porta `8765` no firewall para a rede externa.

---

# 📁 Onde ficam os áudios

Os áudios são enviados ao Anki pelo AnkiConnect (`storeMediaFile`) e vão para a pasta `collection.media` do seu perfil, onde o Anki guarda todas as mídias. Isso vale também no Docker.

Uma cópia temporária fica em `~/anki_tts_temp` (dentro do container, no caso do Docker).

---

# 🛠 Solução de problemas

| Problema                                     | O que fazer                                                                                                                  |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `não consegui conectar ao AnkiConnect`       | Abra o Anki, confirme que o AnkiConnect está instalado e (no Docker/Linux) revise o `webBindAddress`.                         |
| `Nenhum card encontrado`                     | Nenhuma nota tem a tag `audio`. Confira com `tag:audio` no navegador do Anki.                                                 |
| `a biblioteca 'pydub' não está instalada`    | Rode `pip install -r requirements.txt` e instale o ffmpeg.                                                                    |
| Falha ao gerar o áudio (Edge-TTS)            | Confira a internet e atualize a biblioteca: `pip install -U edge-tts`. O serviço da Microsoft muda de vez em quando.          |
| Campo não atualiza                           | Feche o Navegador do Anki (a janela "Procurar") antes de rodar. O AnkiConnect pode falhar ao editar uma nota aberta nele.     |
| O áudio não toca no card                     | Confira se o template tem `{{FrontAudio}}`, `{{BackAudio}}` etc., e se o autoplay do Anki está ativo.                          |
