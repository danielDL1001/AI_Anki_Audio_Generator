import requests
import asyncio
import os
import re
import html
import subprocess
from pathlib import Path

# =========================
# CONFIG
# =========================

VOICE = "pt-BR-FranciscaNeural"

HOME = os.path.expanduser("~")

TEMP_DIR = os.path.join(
    HOME,
    "anki_tts_temp"
)
os.makedirs(TEMP_DIR, exist_ok=True)


# Quantas tentativas antes de desistir
MAX_RETRIES = 3

# =========================
# LIMPAR TEXTO
# =========================

def limpar_texto(texto):

    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\[sound:[^\]]+\]", " ", texto)
    texto = re.sub(r"http\S+", " ", texto)

    texto = html.unescape(texto)

    texto = texto.replace("\u200b", " ")
    texto = texto.replace("\ufeff", " ")

    texto = texto.replace("|", " ")
    texto = texto.replace("*", " ")
    texto = texto.replace("#", " ")
    texto = texto.replace("•", " ")

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()

# =========================
# EDGE TTS
# =========================

async def gerar_audio(texto, arquivo):

    processo = await asyncio.create_subprocess_exec(
        "edge-tts",
        "--voice", VOICE,
        "--text", texto,
        "--write-media", arquivo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout, stderr = await processo.communicate()

    return (
        processo.returncode,
        stdout.decode(),
        stderr.decode()
    )

# =========================
# ANKICONNECT
# =========================

def invoke(action, **params):

    resposta = requests.post(
        "http://localhost:8765",
        json={
            "action": action,
            "version": 6,
            "params": params
        }
    )

    return resposta.json()

# =========================
# PEGAR NOTES
# =========================

notes = invoke(
    "findNotes",
    query="tag:audio"
)["result"]

infos = invoke(
    "notesInfo",
    notes=notes
)["result"]

TOTAL = len(infos)

print(f"\nTOTAL DE CARDS: {TOTAL}\n")

# =========================
# LOOP
# =========================

for i, note in enumerate(infos, start=1):

    note_id = note["noteId"]

    print("=" * 60)
    print(f"[{i}/{TOTAL}]")

    # -------------------------
    # VERIFICA CAMPO
    # -------------------------

    if "Verso" not in note["fields"]:
        print("Sem campo 'Verso'")
        continue

    texto = limpar_texto(
        note["fields"]["Verso"]["value"]
    )

    if not texto:
        print("Texto vazio")
        continue

    nome_audio = f"{note_id}.mp3"

    caminho_audio = os.path.join(
        TEMP_DIR,
        nome_audio
    )

    # -------------------------
    # PULA SE JÁ EXISTIR
    # -------------------------

    campo_audio = ""

    if "Audio" in note["fields"]:
        campo_audio = note["fields"]["Audio"]["value"]

    audio_tag = f"[sound:{nome_audio}]"

    # -------------------------
    # SE O ARQUIVO EXISTE
    # -------------------------

    if (
        os.path.exists(caminho_audio)
        and os.path.getsize(caminho_audio) > 0
    ):

        print(f"Áudio já existe -> {nome_audio}")

        # -------------------------
        # CAMPO VAZIO?
        # -------------------------

        if audio_tag not in campo_audio:

            print("Corrigindo campo Audio...")

            invoke(
                "updateNoteFields",
                note={
                    "id": note_id,
                    "fields": {
                        "Audio": audio_tag
                    }
                }
            )

            print("Campo corrigido.")

        continue

    print(f"Gerando áudio...")
    print(f"Texto: {texto[:80]}")

    sucesso = False

    # =========================
    # RETRY
    # =========================

    for tentativa in range(1, MAX_RETRIES + 1):

        print(f"Tentativa {tentativa}/{MAX_RETRIES}")

        try:

            retorno, out, err = asyncio.run(
                gerar_audio(
                    texto,
                    caminho_audio
                )
            )

            # -------------------------
            # VERIFICA
            # -------------------------

            if (
                retorno == 0
                and os.path.exists(caminho_audio)
                and os.path.getsize(caminho_audio) > 0
            ):

                invoke(
                    "storeMediaFile",
                    filename=nome_audio,
                    path=caminho_audio
                )

                sucesso = True
                break
                

            else:

                print("Falha Edge-TTS")
                print(err)

        except Exception as e:

            print(f"EXCEPTION: {e}")

    # =========================
    # FALHOU
    # =========================

    if not sucesso:

        print("ERRO FINAL")
        continue

    # =========================
    # UPDATE ANKI
    # =========================

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

    print(f"OK -> {nome_audio}")

print("\nFINALIZADO")