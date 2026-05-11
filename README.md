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

# 🧠 Criar o campo Audio

Seu modelo de card precisa ter um campo chamado:

```text
Audio
```

---

# ➕ Como adicionar o campo Audio

Abra qualquer card.

Depois vá em:

```text
Editar → Cards... → Fields... → Add
```

Digite:

```text
Audio
```

Clique em:

```text
OK
```

---

# 🎴 Mostrar o áudio no card

Ainda em:

```text
Cards...
```

Adicione:

```html
{{Audio}}
```

na frente ou no verso do card.

Exemplo:

```html
{{Verso}}

{{Audio}}
```

---

# ▶ Executar

Abra o Anki primeiro.

Depois rode:

```bash
python3 anki_edge_tts.py
```

---

# ✅ Resultado

O script irá:

- encontrar cards com tag `audio`
- ler o campo `Verso`
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

Outras vozes:

- `pt-BR-AntonioNeural`
- `pt-BR-BrendaNeural`
- `ja-JP-NanamiNeural`
- `ja-JP-AoiNeural`

---

# 📁 Local dos áudios

Os arquivos são salvos automaticamente em:

```text
~/.local/share/Anki2/User 1/collection.media
```

---