import requests
import os
import asyncio

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
    texto = note["fields"]["Verso"]["value"]

    # REMOVE HTML
    texto = texto.replace("<br>", " ")
    texto = texto.replace("<div>", " ")
    texto = texto.replace("</div>", " ")

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