import requests
import asyncio
import os
import re
import html
import subprocess

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

MAX_RETRIES = 3

# =========================
# ESCOLHA DO USUÁRIO
# =========================

print("\nO que deseja gerar?\n")
print("1 - Frente")
print("2 - Verso")
print("3 - Frente e Verso\n")

opcao = input("Escolha: ").strip()

if opcao == "1":
    CAMPOS = ["Frente"]

elif opcao == "2":
    CAMPOS = ["Verso"]

elif opcao == "3":
    CAMPOS = ["Frente", "Verso"]

else:
    print("Opção inválida.")
    exit()

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

# =========================
# VALIDAR TAG AUDIO
# =========================

if TOTAL == 0:

    print("\n" + "=" * 60)
    print("ERRO: Nenhum card encontrado.")
    print("=" * 60)

    print("""
O script procura SOMENTE cards com a tag:

audio

Como resolver:

1. Abra o navegador do Anki
2. Selecione seus cards
3. Vá em:
   Notas -> Adicionar etiquetas
4. Adicione a tag:

audio

5. Teste pesquisando:

tag:audio
""")

    exit()

# =========================
# VALIDAR CAMPOS
# =========================

campos_obrigatorios = []

if "Frente" in CAMPOS:
    campos_obrigatorios.append("AudioFrente")

if "Verso" in CAMPOS:
    campos_obrigatorios.append("AudioVerso")

primeira_note = infos[0]

campos_faltando = []

for campo in campos_obrigatorios:

    if campo not in primeira_note["fields"]:
        campos_faltando.append(campo)

if campos_faltando:

    print("\n" + "=" * 60)
    print("ERRO: Campos obrigatórios não encontrados.")
    print("=" * 60)

    print("\nCampos faltando:")

    for campo in campos_faltando:
        print(f"- {campo}")

    print("""

Como resolver:

1. Abra qualquer card no Anki
2. Vá em:
   Editar -> Cards... -> Fields... -> Add

3. Crie os campos faltando

Exemplo:
- AudioFrente
- AudioVerso

4. Depois adicione no template:

{{AudioFrente}}
{{AudioVerso}}

""")

    exit()

print(f"\nTOTAL DE CARDS: {TOTAL}\n")

# =========================
# LOOP
# =========================

for i, note in enumerate(infos, start=1):

    note_id = note["noteId"]

    print("=" * 60)
    print(f"[{i}/{TOTAL}]")

    for campo in CAMPOS:

        # -------------------------
        # VERIFICA CAMPO
        # -------------------------

        if campo not in note["fields"]:
            print(f"Sem campo '{campo}'")
            continue

        texto = limpar_texto(
            note["fields"][campo]["value"]
        )

        if not texto:
            print(f"{campo} vazio")
            continue

        nome_audio = f"{note_id}_{campo}.mp3"

        caminho_audio = os.path.join(
            TEMP_DIR,
            nome_audio
        )

        # -------------------------
        # CAMPO AUDIO
        # -------------------------

        audio_tag = f"[sound:{nome_audio}]"

        if campo == "Frente":
            campo_destino = "AudioFrente"

        elif campo == "Verso":
            campo_destino = "AudioVerso"

        else:
            campo_destino = "Audio"

        # -------------------------
        # SE JÁ EXISTE
        # -------------------------

        if (
            os.path.exists(caminho_audio)
            and os.path.getsize(caminho_audio) > 0
        ):

            print(f"Áudio já existe -> {nome_audio}")

            campo_existente = ""

            if campo_destino in note["fields"]:
                campo_existente = note["fields"][campo_destino]["value"]

            if audio_tag not in campo_existente:

                invoke(
                    "updateNoteFields",
                    note={
                        "id": note_id,
                        "fields": {
                            campo_destino: audio_tag
                        }
                    }
                )

            continue

        print(f"\nGerando {campo}...")
        print(f"Texto: {texto[:80]}")

        sucesso = False

        for tentativa in range(1, MAX_RETRIES + 1):

            print(f"Tentativa {tentativa}/{MAX_RETRIES}")

            try:

                retorno, out, err = asyncio.run(
                    gerar_audio(
                        texto,
                        caminho_audio
                    )
                )

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

        if not sucesso:

            print("ERRO FINAL")
            continue

        # -------------------------
        # UPDATE AUDIO
        # -------------------------

        invoke(
            "updateNoteFields",
            note={
                "id": note_id,
                "fields": {
                    campo_destino: audio_tag
                }
            }
        )

        print(f"OK -> {nome_audio}")

print("\nFINALIZADO")