import requests
import os
import asyncio
import requests
import os
import asyncio
import re
import html

# =========================
# CONFIGURAÇÕES
# =========================

VOICE = "pt-BR-FranciscaNeural"

HOME = os.path.expanduser("~")

# Pasta oficial de mídia do Anki
PASTA = os.path.join(
    HOME,
    ".local/share/Anki2/User 1/collection.media"
)
os.makedirs(PASTA, exist_ok=True)

# =========================
# LIMPAR TEXTO
# =========================

def limpar_texto(texto):

    # Remove tags HTML
    texto = re.sub(r"<[^>]+>", " ", texto)

    # Remove áudio do Anki
    texto = re.sub(r"\[sound:[^\]]+\]", " ", texto)

    # Remove URLs
    texto = re.sub(r"http\S+", " ", texto)

    # Converte entidades HTML
    texto = html.unescape(texto)

    # Remove caracteres invisíveis
    texto = texto.replace("\u200b", " ")
    texto = texto.replace("\ufeff", " ")

    # Remove símbolos muito problemáticos pro TTS
    texto = texto.replace("|", " ")
    texto = texto.replace("*", " ")
    texto = texto.replace("#", " ")
    texto = texto.replace("•", " ")

    # Remove múltiplos espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()

# =========================
# GERAR ÁUDIO
# =========================

async def gerar_audio(texto, arquivo):

    comando = (
        f'edge-tts --voice "{VOICE}" '
        f'--text "{texto}" '
        f'--write-media "{arquivo}"'
    )

    os.system(comando)

# =========================
# ANKICONNECT
# =========================

def invoke(action, **params):

    return requests.post(
        "http://localhost:8765",
        json={
            "action": action,
            "version": 6,
            "params": params
        }
    ).json()

# =========================
# PEGAR APENAS TAG AUDIO
# =========================

notes = invoke(
    "findNotes",
    query="tag:audio"
)["result"]

infos = invoke(
    "notesInfo",
    notes=notes
)["result"]

# =========================
# LOOP
# =========================

for note in infos:

    note_id = note["noteId"]

    # PEGA TEXTO DO VERSO
    if "Verso" in note["fields"]:
        texto = note["fields"]["Verso"]["value"]
    else:
        print(f"Nota sem campo 'Verso': {note['id']}")
        continue

    # LIMPA TEXTO
    texto = limpar_texto(texto)
    nome_audio = f"{note_id}.mp3"

    caminho_audio = os.path.join(
        PASTA,
        nome_audio
    )

    # VERIFICA SE O ÁUDIO EXISTE
    if os.path.exists(caminho_audio):
        print(f"Já existe -> {texto}")
        continue

    # GERA ÁUDIO
    asyncio.run(
        gerar_audio(
            texto,
            caminho_audio
        )
    )

    audio_tag = f"[sound:{nome_audio}]"

    # ESCREVE NO CAMPO AUDIO
    invoke(
        "updateNoteFields",
        note={
            "id": note_id,
            "fields": {
                "Audio": audio_tag
            }
        }
    )

    print(f"OK -> {texto}")