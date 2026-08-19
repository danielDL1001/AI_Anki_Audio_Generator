import requests
import asyncio
import os
import re
import html
import subprocess

try:
    from pydub import AudioSegment
except ImportError:
    print("\nERRO: a biblioteca 'pydub' não está instalada.")
    print("Instale com: pip install pydub")
    print("(também é necessário ter o 'ffmpeg' instalado no sistema)\n")
    exit()

# =========================
# CONFIG
# =========================

VOICE = "pt-BR-FranciscaNeural"

# Duração da pausa (silêncio) que substitui o {{c1::...}} no áudio da
# pergunta, em milissegundos. 1000 = 1 segundo.
CLOZE_PAUSA_MS = 20

# Bitrate usado ao exportar o MP3 final do Cloze_audio pelo pydub.
# Só o Cloze passa pelo pydub (precisa juntar segmentos + silêncio), então
# usamos um bitrate mais alto para minimizar a perda na recompressão.
CLOZE_EXPORT_BITRATE = "192k"

HOME = os.path.expanduser("~")

TEMP_DIR = os.path.join(
    HOME,
    "anki_tts_temp"
)

os.makedirs(TEMP_DIR, exist_ok=True)

MAX_RETRIES = 3

# =========================
# TIPOS DE NOTA SUPORTADOS
# =========================
#
# "tipo": "normal" -> lê o campo diretamente (Basic_audio)
#          -> áudio gerado DIRETO pelo edge-tts, sem passar pelo pydub,
#             pois não há pausas de cloze para juntar. Isso preserva a
#             qualidade original do MP3 (evita decodificar e reexportar).
# "tipo": "cloze"  -> lê o campo com cloze, tratando {{c1::...}} de forma especial
#          -> aqui o pydub é necessário, pois é preciso concatenar
#             segmentos de fala com trechos de silêncio real no meio.
#
# pergunta_campo / resposta_campo = campos de ORIGEM (onde está o texto)
# pergunta_destino / resposta_destino = campos de DESTINO (onde o áudio é salvo)
#
# Para Cloze_audio, o campo de origem do cloze é sempre "Texto" (é onde
# ficam os marcadores {{cN::...}}). O campo "Extra" é texto livre adicional
# que é somado ao áudio de resposta.

NOTE_TYPES = {
    "Basic_audio": {
        "tipo": "normal",
        "pergunta_campo": "Frente",
        "resposta_campo": "Verso",
        "pergunta_destino": "AudioFrente",
        "resposta_destino": "AudioVerso",
    },
    "Cloze_audio": {
        "tipo": "cloze",
        "pergunta_campo": "Texto",
        "resposta_campo": "Extra",
        "pergunta_destino": "AudioTexto",
        "resposta_destino": "AudioExtra",
    },
}

# Regex para capturar {{c1::conteudo}} ou {{c1::conteudo::dica}}
CLOZE_REGEX = re.compile(r"\{\{c\d+::(.*?)\}\}", re.DOTALL)


def extrair_respostas_cloze(texto):
    """Retorna a lista de conteúdos escondidos em {{cN::conteudo}},
    ignorando a parte de dica (depois do segundo '::')."""

    respostas = []

    for bruto in CLOZE_REGEX.findall(texto):
        conteudo = bruto.split("::")[0].strip()

        if conteudo:
            respostas.append(conteudo)

    return respostas


def remover_cloze(texto):
    """Remove completamente {{cN::conteudo::dica}} do texto, incluindo o
    conteúdo (usado no áudio da pergunta, que não pode revelar a resposta)."""

    return CLOZE_REGEX.sub(" ", texto)


def dividir_em_segmentos_cloze(texto):
    """Divide o texto da pergunta em segmentos de fala, marcando com
    ("pausa", None) os pontos onde havia um {{cN::conteudo}}.

    Isso permite que, no áudio final, o trecho escondido vire silêncio
    real, em vez de ser simplesmente pulado/ignorado."""

    segmentos = []
    ultimo_fim = 0

    for match in CLOZE_REGEX.finditer(texto):

        trecho = texto[ultimo_fim:match.start()]

        if trecho.strip():
            segmentos.append(("texto", trecho))

        segmentos.append(("pausa", None))

        ultimo_fim = match.end()

    resto = texto[ultimo_fim:]

    if resto.strip():
        segmentos.append(("texto", resto))

    return segmentos


# =========================
# ESCOLHA DO USUÁRIO
# =========================

print("\nO que deseja gerar?\n")
print("1 - Pergunta")
print("2 - Resposta")
print("3 - Pergunta e Resposta\n")

opcao = input("Escolha: ").strip()

if opcao == "1":
    PAPEIS = ["pergunta"]

elif opcao == "2":
    PAPEIS = ["resposta"]

elif opcao == "3":
    PAPEIS = ["pergunta", "resposta"]

else:
    print("Opção inválida.")
    exit()

# =========================
# LIMPAR TEXTO
# =========================
# def trocar_x_por_vezes(texto):
#     return re.sub(r"(?<=[\d])[\s\xa0]*[x×X][\s\xa0]*(?=[\d])", " vezes ", texto)

def limpar_texto(texto):

    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\[sound:[^\]]+\]", " ", texto)
    texto = re.sub(r"http\S+", " ", texto)
    texto = html.unescape(texto)
    # texto = trocar_x_por_vezes(texto)
    texto = texto.replace("\u200b", " ")
    texto = texto.replace("\ufeff", " ")

    texto = texto.replace("|", " ")
    texto = texto.replace("*", " ")
    texto = texto.replace("#", " ")
    texto = texto.replace("•", " ")

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


async def gerar_audio_unico(texto, arquivo):
    """
    Gera o áudio de um texto simples (sem pausas de cloze) DIRETO no
    arquivo final, escrito pelo próprio edge-tts.

    Usado para notas do tipo "normal" (Basic_audio). Como não há nada
    para concatenar, não faz sentido passar o resultado pelo pydub: isso
    só decodificaria e reexportaria o MP3 (perda de qualidade
    desnecessária). Aqui o arquivo final é exatamente o que o edge-tts
    gerou, com retry em caso de falha.
    """

    ultimo_erro = ""

    for tentativa in range(1, MAX_RETRIES + 1):

        try:
            retorno, out, err = await gerar_audio(texto, arquivo)

            if (
                retorno == 0
                and os.path.exists(arquivo)
                and os.path.getsize(arquivo) > 0
            ):
                return True, None

            ultimo_erro = err

        except Exception as e:
            ultimo_erro = str(e)

    return False, f"Falha ao gerar áudio: {ultimo_erro}"


async def gerar_audio_segmentado(segmentos, arquivo_final):
    """
    Gera o áudio final a partir de uma lista de segmentos no formato:

        [("texto", "algum texto"), ("pausa", None), ("texto", "outro texto")]

    - Cada segmento ("texto", ...) é sintetizado normalmente via Edge-TTS.
    - Cada segmento ("pausa", None) vira silêncio REAL no áudio final (em
      vez de simplesmente não existir).

    Usado apenas para o Cloze_audio, onde é indispensável juntar pedaços
    de fala com silêncio no meio -- por isso é o único caso em que
    passamos pelo pydub. A exportação final usa CLOZE_EXPORT_BITRATE para
    minimizar a perda de qualidade dessa recompressão.

    Retorna (sucesso: bool, mensagem_erro: str | None).
    """

    SILENCIO = AudioSegment.silent(duration=CLOZE_PAUSA_MS)

    audio_final = AudioSegment.silent(duration=0)
    algum_audio_gerado = False
    ultimo_erro = ""

    for indice, (tipo, conteudo) in enumerate(segmentos):

        if tipo == "pausa":
            audio_final += SILENCIO
            continue

        texto_segmento = (conteudo or "").strip()

        if not texto_segmento:
            continue

        caminho_temp = f"{arquivo_final}.part{indice}.mp3"

        sucesso_segmento = False

        for tentativa in range(1, MAX_RETRIES + 1):

            try:
                retorno, out, err = await gerar_audio(texto_segmento, caminho_temp)

                if (
                    retorno == 0
                    and os.path.exists(caminho_temp)
                    and os.path.getsize(caminho_temp) > 0
                ):
                    sucesso_segmento = True
                    break

                ultimo_erro = err

            except Exception as e:
                ultimo_erro = str(e)

        if not sucesso_segmento:
            return False, f"Falha ao gerar segmento de áudio: {ultimo_erro}"

        try:
            audio_final += AudioSegment.from_file(caminho_temp, format="mp3")
            algum_audio_gerado = True
        finally:
            try:
                os.remove(caminho_temp)
            except Exception:
                pass

    if not algum_audio_gerado:
        return False, "Nenhum segmento de áudio foi gerado"

    audio_final.export(
        arquivo_final,
        format="mp3",
        bitrate=CLOZE_EXPORT_BITRATE
    )

    return True, None

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

if len(infos) == 0:

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
# AGRUPAR POR TIPO DE NOTA E VALIDAR
# =========================

notas_por_modelo = {}

for note in infos:
    notas_por_modelo.setdefault(note["modelName"], []).append(note)

infos_processaveis = []

for model_name, notas in notas_por_modelo.items():

    if model_name not in NOTE_TYPES:
        print(f"Aviso: tipo de nota '{model_name}' não suportado. "
              f"Ignorando {len(notas)} nota(s) desse tipo.")
        continue

    config = NOTE_TYPES[model_name]

    # Campos de ORIGEM necessários para os papéis escolhidos
    campos_origem_necessarios = set()

    if "pergunta" in PAPEIS:
        campos_origem_necessarios.add(config["pergunta_campo"])

    if "resposta" in PAPEIS:
        if config["tipo"] == "cloze":
            # no cloze, a resposta também é extraída do campo de pergunta (Texto)
            campos_origem_necessarios.add(config["pergunta_campo"])
        else:
            campos_origem_necessarios.add(config["resposta_campo"])

    amostra = notas[0]
    faltando = [c for c in campos_origem_necessarios if c not in amostra["fields"]]

    if faltando:
        print(f"Aviso: notas '{model_name}' sem os campos {faltando}. "
              f"Ignorando {len(notas)} nota(s) desse tipo.")
        print(f"""
Como resolver (para '{model_name}'):

1. Abra qualquer card desse tipo no Anki
2. Vá em:
   Editar -> Cards... -> Fields... -> Add
3. Crie os campos faltando: {", ".join(faltando)}
""")
        continue

    infos_processaveis.extend(notas)

if not infos_processaveis:
    print("\nNenhuma nota processável encontrada. Encerrando.")
    exit()

TOTAL = len(infos_processaveis)

print(f"\nTOTAL DE CARDS PROCESSÁVEIS: {TOTAL}\n")

# =========================
# VERIFICAR ÁUDIOS EXISTENTES
# =========================

audios_existentes = False

for note in infos_processaveis:

    config = NOTE_TYPES[note["modelName"]]

    for papel in PAPEIS:

        campo_destino = config[f"{papel}_destino"]

        if campo_destino not in note["fields"]:
            continue

        valor = note["fields"][campo_destino]["value"].strip()

        if valor:
            audios_existentes = True
            break

    if audios_existentes:
        break

# =========================
# PERGUNTAR REFAZER
# =========================

REFAZER_AUDIOS = False

if audios_existentes:

    print("=" * 60)
    print("Áudios existentes detectados!")
    print("=" * 60)

    print("""
O que deseja fazer?

1 - Ignorar áudios existentes
2 - Refazer todos os áudios
""")

    escolha_refazer = input("Escolha: ").strip()

    if escolha_refazer == "2":
        REFAZER_AUDIOS = True

# =========================
# LOOP PRINCIPAL
# =========================

for i, note in enumerate(infos_processaveis, start=1):

    note_id = note["noteId"]
    model_name = note["modelName"]
    config = NOTE_TYPES[model_name]

    print("=" * 60)
    print(f"[{i}/{TOTAL}] ({model_name})")

    for papel in PAPEIS:

        campo_destino = config[f"{papel}_destino"]

        # -------------------------
        # MONTAR O TEXTO A SER FALADO
        # -------------------------

        if config["tipo"] == "normal":

            campo_origem = config[f"{papel}_campo"]

            if campo_origem not in note["fields"]:
                print(f"Sem campo '{campo_origem}'")
                continue

            texto = limpar_texto(note["fields"][campo_origem]["value"])

            segmentos = [("texto", texto)]

        else:  # tipo == "cloze"

            campo_texto = config["pergunta_campo"]  # sempre "Texto"

            if campo_texto not in note["fields"]:
                print(f"Sem campo '{campo_texto}'")
                continue

            valor_texto = note["fields"][campo_texto]["value"]

            if papel == "pergunta":

                # Divide a frase em pedaços de fala, marcando com uma
                # "pausa" cada trecho onde havia um {{cN::...}}. A pausa
                # vira silêncio real no áudio (não revela a resposta).
                segmentos = []

                for tipo_seg, conteudo_seg in dividir_em_segmentos_cloze(valor_texto):

                    if tipo_seg == "pausa":
                        segmentos.append(("pausa", None))
                    else:
                        texto_limpo = limpar_texto(conteudo_seg)
                        if texto_limpo:
                            segmentos.append(("texto", texto_limpo))

            else:  # papel == "resposta"

                # Lê o conteúdo que estava escondido em {{cN::conteudo}},
                # limpando cada trecho (remove tags HTML etc.) antes de juntar
                respostas = extrair_respostas_cloze(valor_texto)
                respostas_limpas = [limpar_texto(r) for r in respostas]
                texto_respostas = ", ".join([r for r in respostas_limpas if r])

                # E soma o que estiver digitado manualmente no campo Extra
                campo_extra = config["resposta_campo"]  # "Extra"
                valor_extra = note["fields"].get(campo_extra, {}).get("value", "")
                texto_extra = limpar_texto(valor_extra)

                partes = [p for p in [texto_respostas, texto_extra] if p]
                texto = ". ".join(partes)

                segmentos = [("texto", texto)]

        # Texto "achatado" (só os pedaços falados, sem marcar as pausas),
        # usado para checagem de vazio/validação e para o preview no console
        texto = " ".join(
            conteudo for tipo_seg, conteudo in segmentos if tipo_seg == "texto"
        ).strip()

        if not texto:
            print(f"{campo_destino} vazio")
            continue

        # =========================
        # VALIDAR TEXTO FALÁVEL
        # =========================

        texto_validacao = re.sub(
            r"[^\w\sÀ-ÿ]",
            "",
            texto
        )

        if not texto_validacao.strip():
            print(f"{campo_destino} contém apenas símbolos inválidos")
            continue

        # label usado no nome do arquivo (mantém compatibilidade com
        # arquivos antigos do Basic_audio: 123456_Frente.mp3 etc.)
        label = campo_destino[5:] if campo_destino.startswith("Audio") else campo_destino

        nome_audio = f"{note_id}_{label}.mp3"

        caminho_audio = os.path.join(
            TEMP_DIR,
            nome_audio
        )

        audio_tag = f"[sound:{nome_audio}]"

        # -------------------------
        # SE JÁ EXISTE
        # -------------------------

        if (
            os.path.exists(caminho_audio)
            and os.path.getsize(caminho_audio) > 0
        ):

            # -------------------------
            # IGNORAR ÁUDIO EXISTENTE
            # -------------------------

            if not REFAZER_AUDIOS:

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

            # -------------------------
            # REFAZER ÁUDIO
            # -------------------------

            else:

                print(f"Refazendo áudio -> {nome_audio}")

                try:
                    os.remove(caminho_audio)
                except Exception:
                    pass

        print(f"\nGerando {papel} ({campo_destino})...")
        print(f"Texto: {texto[:80]}")

        if config["tipo"] == "normal":

            # Basic_audio: sem pausas de cloze -> gera direto com o
            # Edge-TTS, sem passar pelo pydub (evita perda de qualidade
            # por recompressão do MP3).
            sucesso, erro = asyncio.run(
                gerar_audio_unico(
                    texto,
                    caminho_audio
                )
            )

        else:

            # Cloze_audio: precisa juntar segmentos de fala com pausas
            # reais de silêncio -> só aqui é necessário usar o pydub.
            sucesso, erro = asyncio.run(
                gerar_audio_segmentado(
                    segmentos,
                    caminho_audio
                )
            )

        if sucesso:

            invoke(
                "storeMediaFile",
                filename=nome_audio,
                path=caminho_audio
            )

        else:

            print("Falha Edge-TTS")
            print(erro)
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