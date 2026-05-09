import requests
import os
import asyncio

# Configurações
VOICE = "pt-BR-FranciscaNeural" #Or: VOICE = "ja-JP-AoiNeural",ja-JP-NanamiNeural"
HOME = os.path.expanduser("~")
PASTA = os.path.join(
    HOME,
    "Downloads",
    "AudioAnki"
)
# Criar a pasta se não existir
os.makedirs(PASTA, exist_ok=True)

# Funções
async def gerar_audio(texto, arquivo):

    comando = (
        f'edge-tts --voice "{VOICE}" '
        f'--text "{texto}" '
        f'--write-media "{arquivo}"'
    )

    os.system(comando)

def invoke(action, **params):

    return requests.post(
        "http://localhost:8765",
        json={
            "action": action,
            "version": 6,
            "params": params
        }
    ).json()

notes = invoke(
    "findNotes",
    query=""
)["result"]

infos = invoke(
    "notesInfo",
    notes=notes
)["result"]

for note in infos:

    note_id = note["noteId"]

    texto = note["fields"]["Frente"]["value"]

    nome_audio = f"{note_id}.mp3"

    caminho_audio = os.path.join(
        PASTA,
        nome_audio
    )

    asyncio.run(
        gerar_audio(
            texto,
            caminho_audio
        )
    )

    audio_tag = f"[sound:{nome_audio}]"

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