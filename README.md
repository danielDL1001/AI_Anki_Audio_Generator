# Anki-Audio-Generator

Generate speech audio automatically for your Anki cards using Edge-TTS + AnkiConnect.

---

# 📦 Requisitos

- Python 3.10+
- Anki
- Addon AnkiConnect
- Requests
- Edge-TTS

---

# 🔧 Instalação

```bash
git clone https://github.com/danielDL1001/Anki-Audio-Generator.git

cd Anki-Audio-Generator

python -m venv .venv

source .venv/bin/activate

pip install requests edge-tts
```

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

Ele gera áudio SOMENTE para cards que possuem a tag:

```text
audio
```

---

# 🏷 Como criar a tag `audio`

## 1. Abrir o navegador do Anki

Clique em:

```text
Procurar
```

ou pressione:

```text
B
```

---

## 2. Selecionar os cards

Selecione:

- um card
- vários cards
- ou um deck inteiro

---

## 3. Adicionar a tag

Na barra superior:

```text
Notas → Adicionar etiquetas...
```

ou use:

```text
Ctrl + Shift + A
```

Digite:

```text
audio
```

Clique em:

```text
OK
```

Pronto.

Agora esses cards serão detectados automaticamente pelo script.

---

# 🔎 Testar se a tag foi criada

No navegador do Anki, pesquise:

```text
tag:audio
```

Se os cards aparecerem, está funcionando corretamente.

---

# 🧠 Criar os campos de áudio

Seu modelo de card precisa ter os campos:

```text
AudioFrente
AudioVerso
```

Esses campos são usados para separar os áudios da frente e do verso do card.

Isso evita:

- áudio tocando fora de ordem
- dois áudios tocando juntos
- áudio da frente tocando no verso
- problemas de autoplay no Anki

---

# ➕ Como adicionar os campos

Abra qualquer card.

Depois vá em:

```text
Editar → Cards... → Fields... → Add
```

Crie os dois campos:

## Campo 1

```text
AudioFrente
```

## Campo 2

```text
AudioVerso
```

Clique em:

```text
OK
```

---

# 🎴 Mostrar os áudios no card

O áudio NÃO irá tocar automaticamente se o template do card não possuir:

```html
{{AudioFrente}}
```

e

```html
{{AudioVerso}}
```

Você PRECISA adicionar isso no template do cartão.

---

# ➕ Como adicionar `{{AudioFrente}}` e `{{AudioVerso}}`

Abra qualquer card.

Depois vá em:

```text
Editar → Cards...
```

Você verá algo parecido com:

## Frente

```html
{{Frente}}
```

## Verso

```html
{{FrontSide}}

<hr id=answer>

{{Verso}}
```

---

# ✅ Template recomendado

## Frente

```html
{{Frente}}

{{AudioFrente}}
```

---

## Verso

```html
{{FrontSide}}

<hr id=answer>

{{Verso}}

{{AudioVerso}}
```

---

# ✅ Resultado do card

Quando o card abrir no Anki:

- o áudio da frente tocará apenas na frente
- o áudio do verso tocará apenas no verso
- o autoplay funcionará corretamente
- o script adicionará automaticamente:

```text
[sound:arquivo.mp3]
```

nos campos corretos:

```text
AudioFrente
AudioVerso
```

# ▶ Executar

Abra o Anki primeiro.

Depois rode:

```bash
python3 anki_edge_tts.py
```

---

# 🎛 Escolher o tipo de áudio

Quando o script iniciar, ele perguntará qual campo deve virar áudio:

```text
1 - Frente
2 - Verso
3 - Frente e Verso
```

Exemplo:

```text
O que deseja gerar?

1 - Frente
2 - Verso
3 - Frente e Verso

Escolha:
```

## Opções

### Frente
Gera áudio apenas do campo:

```text
Frente
```

### Verso
Gera áudio apenas do campo:

```text
Verso
```

### Frente e Verso
Gera áudio para os dois campos.

Exemplo de arquivos:

```text
123456_Frente.mp3
123456_Verso.mp3
```

Os dois áudios serão adicionados automaticamente no campo:

```text
Audio
```

---

# ✅ Resultado final

O script irá:

- encontrar cards com tag `audio`
- ler o campo `Frente`, `Verso` ou `Frente e Verso`
- gerar voz automaticamente
- salvar os áudios no Anki
- adicionar automaticamente:

```text
[sound:arquivo.mp3]
```

- tocar automaticamente durante revisão

---

# 🎤 Vozes

Exemplo:

```python
VOICE = "pt-BR-FranciscaNeural"
```

O Edge-TTS possui várias vozes naturais em diferentes idiomas.

---

## 🇧🇷 Português (Brasil)

### Vozes femininas

- `pt-BR-FranciscaNeural`
- `pt-BR-BrendaNeural`

### Vozes masculinas

- `pt-BR-AntonioNeural`
- `pt-BR-DonatoNeural`

---

## 🇺🇸 Inglês

### Vozes femininas

- `en-US-JennyNeural`
- `en-US-AriaNeural`
- `en-US-AnaNeural`
- `en-GB-SoniaNeural`

### Vozes masculinas

- `en-US-GuyNeural`
- `en-US-DavisNeural`
- `en-GB-RyanNeural`

---

## 🇯🇵 Japonês

### Vozes femininas

- `ja-JP-NanamiNeural`
- `ja-JP-AoiNeural`

### Vozes masculinas

- `ja-JP-KeitaNeural`
- `ja-JP-DaichiNeural`

---

## 🇪🇸 Espanhol

### Vozes femininas

- `es-ES-ElviraNeural`
- `es-MX-DaliaNeural`

### Vozes masculinas

- `es-ES-AlvaroNeural`
- `es-MX-JorgeNeural`

---

# 🔄 Como trocar a voz

Abra o arquivo:

```text
anki_edge_tts.py
```

Procure por:

```python
VOICE = "pt-BR-FranciscaNeural"
```

E substitua pela voz desejada.

Exemplo:

```python
VOICE = "ja-JP-NanamiNeural"
```

ou:

```python
VOICE = "en-US-JennyNeural"
```

---

# 🧪 Testar vozes disponíveis

Você também pode listar TODAS as vozes disponíveis do Edge-TTS com:

```bash
edge-tts --list-voices
```

Isso mostrará:

- idioma
- nome da voz
- país
- gênero

---

# 💡 Recomendações

## Para cards normais

```text
pt-BR-FranciscaNeural
```

Natural e confortável para revisões longas.

---

## Para inglês

```text
en-US-JennyNeural
```

Excelente pronúncia e clareza.

---

## Para japonês

```text
ja-JP-NanamiNeural
```

Muito usada para estudo de japonês e anime-style listening.

---

## Para espanhol

```text
es-ES-ElviraNeural
```

Boa dicção e ritmo equilibrado.

---

# 📁 Local dos áudios

Os arquivos são salvos automaticamente em:

```text
~/.local/share/Anki2/User 1/collection.media
```

---