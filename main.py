import requests
import asyncio
import os
import re
import json
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

# Arquivo onde ficam salvos os tipos de nota e campos configurados pelo
# usuário (origem -> destino). Assim, adicionar um campo novo não exige
# editar este script: basta usar o menu "Configurar tipos de nota /
# campos" e a configuração fica salva para as próximas execuções.
CONFIG_FILE = os.path.join(HOME, "anki_tts_config.json")

# =========================
# TIPOS DE NOTA SUPORTADOS
# =========================
#
# Cada tipo de nota tem uma lista de "campos", e cada campo é um par
# origem -> destino com um "papel":
#
#   "normal"         -> lê o campo de origem direto e manda pro TTS.
#                        Áudio gerado DIRETO pelo edge-tts (sem pydub),
#                        preservando a qualidade original do MP3.
#   "cloze_pergunta" -> trata {{c1::...}} como pausa (silêncio real) no
#                        áudio da pergunta. Precisa do pydub para juntar
#                        os pedaços de fala com o silêncio.
#   "cloze_resposta" -> lê o conteúdo escondido em {{c1::...}} (e,
#                        opcionalmente, soma um campo de texto livre via
#                        "extra_origem", ex.: "Extra"). Também usa pydub.
#
# Esses são só os valores padrão usados a primeira vez que o script
# roda (se o arquivo de configuração ainda não existir). Depois disso,
# tudo é lido/editado a partir de CONFIG_FILE pelo menu de configuração.

DEFAULT_CONFIG = {
    "Basic_audio": {
        "campos": [
            {"origem": "Front", "destino": "FrontAudio", "papel": "normal"},
            {"origem": "Back", "destino": "BackAudio", "papel": "normal"},
            {"origem": "Example", "destino": "ExampleAudio", "papel": "normal"},
        ]
    },
    "Cloze_audio": {
        "campos": [
            {"origem": "Text", "destino": "TextAudio", "papel": "cloze_pergunta"},
            {
                "origem": "Text",
                "destino": "ExtraAudio",
                "papel": "cloze_resposta",
                "extra_origem": "Extra",
            },
        ]
    },
}


def carregar_config():
    """Lê o arquivo de configuração do usuário. Se ele ainda não
    existir, começa a partir do padrão (DEFAULT_CONFIG). Tipos de nota
    padrão que o usuário ainda não tenha customizado são sempre
    garantidos, sem sobrescrever o que ele já configurou."""

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

            for model_name, dados in DEFAULT_CONFIG.items():
                config.setdefault(model_name, json.loads(json.dumps(dados)))

            return config

        except Exception:
            print("Aviso: não foi possível ler o arquivo de configuração, usando padrão.")

    return json.loads(json.dumps(DEFAULT_CONFIG))


def salvar_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

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


def obter_campos_modelo(model_name):
    """Pergunta ao Anki (via AnkiConnect) quais são os campos reais do
    tipo de nota `model_name`. É isso que permite montar o menu
    numerado com os nomes de campo de verdade, em vez do usuário ter
    que digitar (e arriscar errar) o nome do campo."""

    resposta = invoke("modelFieldNames", modelName=model_name)
    return resposta.get("result") or []


def garantir_campo_no_modelo(model_name, campo):
    """Garante que `campo` existe no tipo de nota no Anki, criando-o
    automaticamente (via AnkiConnect) se ainda não existir. Isso evita
    ter que criar campos manualmente em Ferramentas -> Gerenciar Tipos
    de Nota toda vez que se configura um novo destino de áudio."""

    if campo in obter_campos_modelo(model_name):
        return True

    resposta = invoke("modelFieldAdd", modelName=model_name, fieldName=campo, index=0)

    if resposta.get("error"):
        print(f"Não foi possível criar o campo '{campo}' automaticamente: {resposta['error']}")
        print(
            f"Crie manualmente em: Ferramentas -> Gerenciar Tipos de Nota -> "
            f"{model_name} -> Campos -> Adicionar -> '{campo}'"
        )
        return False

    print(f"Campo '{campo}' criado automaticamente no tipo de nota '{model_name}'.")
    return True


# =========================
# ASSISTENTE DE CONFIGURAÇÃO
# =========================
# Aqui é onde o usuário personaliza quais campos geram áudio e para
# onde, sem precisar editar o código: os nomes de campo são sempre
# lidos direto do Anki e mostrados como uma lista numerada.

def escolher_da_lista(itens, mensagem):
    """Mostra `itens` numerados (1, 2, 3...) e devolve o item escolhido,
    ou None se o usuário cancelar/errar a opção.

    Aceita tanto o NÚMERO da opção quanto o próprio nome do item
    digitado (comparação sem diferenciar maiúsculas/minúsculas), já que
    é comum digitar o nome do campo em vez do número."""

    print()
    for indice, item in enumerate(itens, start=1):
        print(f"{indice} - {item}")
    print("0 - Cancelar")

    escolha = input(f"\n{mensagem}").strip()

    if escolha == "0" or not escolha:
        return None

    if escolha.isdigit():
        if 1 <= int(escolha) <= len(itens):
            return itens[int(escolha) - 1]
        print("Opção inválida.")
        return None

    # Tenta casar pelo nome digitado (ex.: usuário digitou "Example"
    # em vez de "3")
    for item in itens:
        if item.lower() == escolha.lower():
            return item

    print("Opção inválida.")
    return None


def assistente_adicionar_campo(model_name, campos_modelo):
    """Pergunta um novo par (campo de origem -> campo de áudio de
    destino) para `model_name`, usando os nomes de campo reais do Anki
    (mostrados como 1.(campo1), 2.(campo2), ...) em vez do usuário ter
    que escrever o nome manualmente. Devolve uma lista com 1 ou 2
    campos (1 para campo "normal", 2 para "cloze": pergunta + resposta)."""

    origem = escolher_da_lista(
        campos_modelo,
        f"Qual campo de '{model_name}' contém o TEXTO a ser narrado? "
    )

    if origem is None:
        return None

    eh_cloze = input(
        f"\nO campo '{origem}' usa marcações de cloze, tipo {{{{c1::...}}}}? (s/n): "
    ).strip().lower() == "s"

    if eh_cloze:

        destino_pergunta = input(
            "\nNome do campo de DESTINO para o áudio da PERGUNTA "
            "(o trecho escondido no cloze vira uma pausa/silêncio): "
        ).strip()

        if not destino_pergunta:
            print("Nome inválido, cancelando.")
            return None

        campo_extra = None

        if input(
            "\nExiste um campo de texto extra a somar na resposta "
            "(ex.: um campo 'Extra')? (s/n): "
        ).strip().lower() == "s":
            campo_extra = escolher_da_lista(
                campos_modelo,
                "Qual campo é o texto extra? "
            )

        destino_resposta = input(
            "\nNome do campo de DESTINO para o áudio da RESPOSTA "
            "(conteúdo escondido no cloze, + extra se houver): "
        ).strip()

        if not destino_resposta:
            print("Nome inválido, cancelando.")
            return None

        novos_campos = [
            {"origem": origem, "destino": destino_pergunta, "papel": "cloze_pergunta"},
            {
                "origem": origem,
                "destino": destino_resposta,
                "papel": "cloze_resposta",
                **({"extra_origem": campo_extra} if campo_extra else {}),
            },
        ]

    else:

        destino = input(
            f"\nNome do campo de DESTINO para o áudio de '{origem}' "
            f"(ex.: '{origem}Audio'): "
        ).strip()

        if not destino:
            print("Nome inválido, cancelando.")
            return None

        novos_campos = [{"origem": origem, "destino": destino, "papel": "normal"}]

    for campo in novos_campos:
        garantir_campo_no_modelo(model_name, campo["destino"])

    return novos_campos


def configurar_note_type_interativamente(model_name, config):
    """Menu de configuração de UM tipo de nota: adicionar, remover ou
    revisar campos de áudio. Tudo é salvo em CONFIG_FILE ao final de
    cada alteração."""

    campos_modelo = obter_campos_modelo(model_name)

    if not campos_modelo:
        print(f"Não foi possível ler os campos do tipo de nota '{model_name}' pelo AnkiConnect.")
        return

    config.setdefault(model_name, {"campos": []})

    while True:

        print("\n" + "=" * 60)
        print(f"Configurando tipo de nota: {model_name}")
        print("=" * 60)

        if config[model_name]["campos"]:
            print("\nCampos de áudio configurados:")
            for c in config[model_name]["campos"]:
                print(f"  - {c['origem']} -> {c['destino']} ({c['papel']})")
        else:
            print("\n(nenhum campo configurado ainda)")

        print("""
1 - Adicionar campo de áudio
2 - Remover campo configurado
3 - Concluir
""")

        opcao = input("Escolha: ").strip()

        if opcao == "1":
            novos = assistente_adicionar_campo(model_name, campos_modelo)

            if novos:
                config[model_name]["campos"].extend(novos)
                salvar_config(config)
                print("Campo(s) adicionado(s) e salvo(s) na configuração.")

        elif opcao == "2":
            campos_atuais = config[model_name]["campos"]

            if not campos_atuais:
                print("Nenhum campo configurado para remover.")
                continue

            rotulos = [f"{c['origem']} -> {c['destino']} ({c['papel']})" for c in campos_atuais]
            escolhido = escolher_da_lista(rotulos, "Qual campo remover? ")

            if escolhido:
                indice = rotulos.index(escolhido)
                removido = campos_atuais.pop(indice)
                salvar_config(config)
                print(f"Removido: {removido['origem']} -> {removido['destino']}")

        else:
            break

    salvar_config(config)


def escolher_campos_para_gerar(model_name, campos_config, amostra_fields):
    """Monta dinamicamente o menu "1.(campo1), 2.(campo2), n.(campoN)"
    a partir dos campos JÁ CONFIGURADOS para este tipo de nota (e que
    realmente existem nas notas encontradas), e deixa o usuário
    escolher quais gerar nesta execução."""

    campos_disponiveis = [
        campo for campo in campos_config
        if campo["origem"] in amostra_fields
    ]

    if not campos_disponiveis:
        return []

    rotulo_papel = {
        "normal": "texto",
        "cloze_pergunta": "pergunta com cloze",
        "cloze_resposta": "resposta do cloze",
    }

    print(f"\nTipo de nota: {model_name}")
    print("O que deseja gerar?\n")

    for indice, campo in enumerate(campos_disponiveis, start=1):
        descricao = rotulo_papel.get(campo["papel"], campo["papel"])
        print(f"{indice} - {campo['destino']}  (a partir de '{campo['origem']}', {descricao})")

    opcao_todos = len(campos_disponiveis) + 1
    print(f"{opcao_todos} - Todos")

    escolha = input("\nEscolha (números separados por vírgula, ou 'todos'): ").strip().lower()

    if escolha in ("todos", str(opcao_todos)):
        return campos_disponiveis

    indices_escolhidos = []

    for parte in escolha.split(","):
        parte = parte.strip()
        if parte.isdigit() and 1 <= int(parte) <= len(campos_disponiveis):
            indices_escolhidos.append(int(parte) - 1)

    return [campos_disponiveis[i] for i in indices_escolhidos]

# =========================
# CONVERSÃO CLOZE
# =========================

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
# CONVERSÃO MATHJAX/LATEX -> FALA
# =========================
#
# Objetivo: antes de qualquer coisa ser mandada para o Edge-TTS, qualquer
# fórmula MathJax/LaTeX presente no texto (\( ... \), \[ ... \] e também
# as variantes antigas do Anki [$] ... [/$] e [$$] ... [/$$]) é reescrita
# como uma frase falável em português, tipo "limite de f de x quando x
# tende a a" em vez do código LaTeX cru.
#
# Importante: essas funções NUNCA tocam em note["fields"] (o campo
# original do Anki). Elas só atuam sobre a string local que será enviada
# ao TTS. O cartão continua mostrando a fórmula renderizada normalmente.
#
# A conversão é propositalmente best-effort: cobre os casos comuns de
# Cálculo I (limites, potências, frações, raízes, integrais, somatórios,
# derivadas e os símbolos mais usados). Expressões muito incomuns ou mal
# formadas podem não virar uma frase perfeita, mas o texto nunca fica
# quebrado ou trava o script -- no pior caso, cai num fallback que só
# remove os comandos LaTeX e mantém as letras/números (ver mais abaixo).

NUMEROS_EXTENSO = {
    "0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro",
    "5": "cinco", "6": "seis", "7": "sete", "8": "oito", "9": "nove",
    "10": "dez", "11": "onze", "12": "doze", "13": "treze", "14": "catorze",
    "15": "quinze", "16": "dezesseis", "17": "dezessete", "18": "dezoito",
    "19": "dezenove", "20": "vinte",
}

# Funções/comandos "de um argumento só" que são lidos com o próprio nome
# (o argumento entre parênteses vira "de <argumento>" pelo tratamento
# normal de chamada de função, ex.: sin(x) -> "sen de x").
FUNCOES_CONHECIDAS = {
    "sin": "seno", "cos": "cosseno", "tan": "tangente",
    "sec": "secante", "csc": "cossecante", "cot": "cotangente",
    "sinh": "seno hiperbólico", "cosh": "cosseno hiperbólico",
    "tanh": "tangente hiperbólica",
    "arcsin": "arco seno", "arccos": "arco cosseno", "arctan": "arco tangente",
    "log": "log", "ln": "logaritmo natural", "exp": "exponencial",
}

# Símbolos LaTeX que viram uma palavra/expressão fixa em português.
# Mantido num dicionário só para facilitar adicionar novos símbolos sem
# mexer na lógica de parsing.
SIMBOLOS_LATEX = {
    r"\to": "tende a",
    r"\rightarrow": "tende a",
    r"\infty": "infinito",
    r"\leq": "menor ou igual a",
    r"\le": "menor ou igual a",
    r"\geq": "maior ou igual a",
    r"\ge": "maior ou igual a",
    r"\neq": "diferente de",
    r"\ne": "diferente de",
    r"\pm": "mais ou menos",
    r"\mp": "menos ou mais",
    r"\pi": "pi",
    r"\alpha": "alfa",
    r"\beta": "beta",
    r"\gamma": "gama",
    r"\theta": "teta",
    r"\delta": "delta",
    r"\Delta": "delta",
    r"\cdot": "vezes",
    r"\times": "vezes",
    r"\div": "dividido por",
    r"\approx": "aproximadamente igual a",
    r"\equiv": "equivalente a",
    r"\in": "pertence a",
    r"\forall": "para todo",
    r"\exists": "existe",
    r"\partial": "derivada parcial",
    r"\ldots": "e assim por diante",
    r"\dots": "e assim por diante",
    r"\cdots": "e assim por diante",
}

# Fórmulas delimitadas do jeito que o Anki/MathJax normalmente grava:
# inline \( ... \), bloco \[ ... \], e as variantes antigas [$] ... [/$]
# e [$$] ... [/$$] (algumas coleções antigas do Anki ainda usam isso).
MATHJAX_REGEX = re.compile(
    r"\\\((.*?)\\\)"
    r"|\\\[(.*?)\\\]"
    r"|\[\$\](.*?)\[/\$\]"
    r"|\[\$\$\](.*?)\[/\$\$\]",
    re.DOTALL
)


def _numero_por_extenso(token):
    """Converte um número inteiro (opcionalmente negativo) por extenso.
    Números fora da tabela (ex.: 137) ficam como estão -- é a principal
    limitação conhecida: o Edge-TTS ainda lê dígitos crus razoavelmente
    bem em português, então não é um problema grave."""

    token = token.strip()
    negativo = token.startswith("-")
    valor = token[1:] if negativo else token

    if valor.isdigit():
        extenso = NUMEROS_EXTENSO.get(valor, valor)
        return ("menos " + extenso) if negativo else extenso

    return token


def _extrair_argumento(expr, i):
    """A partir da posição i em expr, extrai um "argumento" ao estilo
    LaTeX:

    - Se for um grupo {...}, retorna o CONTEÚDO (sem as chaves) e o
      índice logo após o '}' de fechamento (lida com chaves aninhadas).
    - Se for um comando \\algo, retorna o comando inteiro.
    - Caso contrário, retorna só o próximo caractere (ex.: em "x^2", o
      expoente sem chaves é só o "2").

    Isso é o que permite lidar com \\frac{a}{b}, \\frac{x^2+1}{x-1},
    x^2, x^{10}, etc. sem depender de uma regex só (que não dá conta de
    chaves aninhadas de forma confiável).
    """

    n = len(expr)

    if i >= n:
        return "", i

    if expr[i] == "{":
        profundidade = 1
        j = i + 1

        while j < n and profundidade > 0:
            if expr[j] == "{":
                profundidade += 1
            elif expr[j] == "}":
                profundidade -= 1
            j += 1

        return expr[i + 1:j - 1], j

    if expr[i] == "\\":
        j = i + 1

        while j < n and expr[j].isalpha():
            j += 1

        return expr[i:j], j

    return expr[i], i + 1


def _encontrar_fechamento(expr, i, abre="(", fecha=")"):
    """A partir de i (apontando para o caractere de abertura), encontra o
    índice do caractere de fechamento correspondente, lidando com
    parênteses aninhados. Se não achar, considera que vai até o fim."""

    profundidade = 0
    n = len(expr)

    for j in range(i, n):
        if expr[j] == abre:
            profundidade += 1
        elif expr[j] == fecha:
            profundidade -= 1
            if profundidade == 0:
                return j

    return n - 1


def _latex_para_fala(expr):
    """Converte recursivamente uma expressão LaTeX (sem os delimitadores
    \\( \\) / \\[ \\]) em uma frase falável em português.

    A ideia geral: percorre a expressão caractere a caractere, e sempre
    que reconhece um comando/estrutura conhecida (\\frac, \\sqrt, \\lim,
    \\int, \\sum, expoente ^, índice _, chamada de função f(...), símbolos
    como \\to/\\infty/\\pi etc.) já produz o pedaço de frase equivalente,
    chamando a si mesma para converter os "argumentos" internos (por
    isso frações como \\frac{x^2+1}{x-1} funcionam: o numerador e o
    denominador também passam pelo mesmo tratamento).
    """

    expr = re.sub(r"\s+", " ", expr.strip())

    resultado = []
    i = 0
    n = len(expr)

    while i < n:
        c = expr[i]

        if c.isspace():
            i += 1
            continue

        # -------------------------
        # Comandos de espaçamento do LaTeX (\, \; \! ...): apenas ignora
        # -------------------------
        if expr[i:i + 2] in (r"\,", r"\;", r"\!"):
            i += 2
            continue

        # -------------------------
        # Comandos \algo
        # -------------------------
        if c == "\\":
            j = i + 1

            while j < n and expr[j].isalpha():
                j += 1

            comando = expr[i:j]
            i = j

            # \left( \right) etc.: são só "decoração" de tamanho do
            # parêntese, o parêntese em si é tratado normalmente a seguir
            if comando in (r"\left", r"\right"):
                continue

            # \frac{a}{b}, \dfrac{a}{b}, \tfrac{a}{b}
            if comando in (r"\frac", r"\dfrac", r"\tfrac"):
                num, i = _extrair_argumento(expr, i)
                den, i = _extrair_argumento(expr, i)

                # Caso especial: notação de derivada d/dx f(x)
                if num.strip() == "d" and re.fullmatch(r"d\s*[a-zA-Z]", den.strip()):
                    variavel = den.strip()[1:].strip()
                    resto = _latex_para_fala(expr[i:])
                    resultado.append(f"derivada de {resto} em relação a {variavel}")
                    i = n
                else:
                    resultado.append(
                        _latex_para_fala(num) + " sobre " + _latex_para_fala(den)
                    )

                continue

            # \sqrt{a} ou \sqrt[n]{a}
            if comando == r"\sqrt":
                indice = None

                if i < n and expr[i] == "[":
                    fim = expr.find("]", i)
                    if fim == -1:
                        fim = i
                    indice = expr[i + 1:fim]
                    i = fim + 1

                conteudo, i = _extrair_argumento(expr, i)
                conteudo_falado = _latex_para_fala(conteudo)

                if indice is None or indice.strip() == "2":
                    resultado.append(f"raiz quadrada de {conteudo_falado}")
                elif indice.strip() == "3":
                    resultado.append(f"raiz cúbica de {conteudo_falado}")
                else:
                    resultado.append(
                        f"raiz de índice {_numero_por_extenso(indice)} de {conteudo_falado}"
                    )

                continue

            # \lim_{x \to a} f(x)
            if comando == r"\lim":
                sub = ""

                if i < n and expr[i] == "_":
                    i += 1
                    sub, i = _extrair_argumento(expr, i)

                resto = _latex_para_fala(expr[i:])
                i = n

                if sub.strip():
                    resultado.append(f"limite de {resto} quando {_latex_para_fala(sub)}")
                else:
                    resultado.append(f"limite de {resto}")

                continue

            # \int_a^b f(x)\,dx  (limites são opcionais)
            if comando == r"\int":
                inferior, superior = "", ""

                if i < n and expr[i] == "_":
                    i += 1
                    inferior, i = _extrair_argumento(expr, i)

                if i < n and expr[i] == "^":
                    i += 1
                    superior, i = _extrair_argumento(expr, i)

                resto = expr[i:]
                i = n

                # separa a diferencial final (dx, dt, du...) do resto
                match_dif = re.search(r"d([a-zA-Z])\s*$", resto.strip())
                variavel = None

                if match_dif:
                    variavel = match_dif.group(1)
                    resto = resto[:match_dif.start()]

                resto_falado = _latex_para_fala(resto)

                if inferior.strip() and superior.strip():
                    frase = (
                        f"integral de {_latex_para_fala(inferior)} "
                        f"até {_latex_para_fala(superior)} de {resto_falado}"
                    )
                else:
                    frase = f"integral de {resto_falado}"

                if variavel:
                    frase += f" diferencial de {variavel}"

                resultado.append(frase)
                continue

            # \sum_{i=1}^{n} i
            if comando == r"\sum":
                inferior, superior = "", ""

                if i < n and expr[i] == "_":
                    i += 1
                    inferior, i = _extrair_argumento(expr, i)

                if i < n and expr[i] == "^":
                    i += 1
                    superior, i = _extrair_argumento(expr, i)

                resto_falado = _latex_para_fala(expr[i:])
                i = n

                if "=" in inferior:
                    variavel, valor_inicial = inferior.split("=", 1)
                    inferior_falado = (
                        f"{_latex_para_fala(variavel)} igual a {_latex_para_fala(valor_inicial)}"
                    )
                else:
                    inferior_falado = _latex_para_fala(inferior)

                superior_falado = _latex_para_fala(superior)

                if inferior_falado.strip() and superior_falado.strip():
                    resultado.append(
                        f"somatório de {inferior_falado} até {superior_falado} de {resto_falado}"
                    )
                else:
                    resultado.append(f"somatório de {resto_falado}")

                continue

            # Símbolos conhecidos (\to, \infty, \pi, \leq, ...)
            if comando in SIMBOLOS_LATEX:
                resultado.append(SIMBOLOS_LATEX[comando])
                continue

            # Comando desconhecido: melhor do que ler o comando cru é
            # falar só o "nome" dele (sem a barra), evitando ler símbolos
            # estranhos em voz alta.
            if len(comando) > 1:
                resultado.append(comando[1:])

            continue

        # -------------------------
        # Expoente: base^expoente
        # -------------------------
        if c == "^":
            i += 1
            expoente, i = _extrair_argumento(expr, i)
            expoente = expoente.strip()

            if expoente == "2":
                resultado.append("ao quadrado")
            elif expoente == "3":
                resultado.append("ao cubo")
            elif re.fullmatch(r"-?\d+", expoente):
                resultado.append(f"elevado a {_numero_por_extenso(expoente)}")
            else:
                resultado.append(f"elevado a {_latex_para_fala(expoente)}")

            continue

        # -------------------------
        # Índice: base_indice (fora do contexto já tratado por
        # \lim/\int/\sum acima)
        # -------------------------
        if c == "_":
            i += 1
            indice, i = _extrair_argumento(expr, i)
            resultado.append(f"índice {_latex_para_fala(indice)}")
            continue

        # -------------------------
        # Grupo solto {...} (sobrou de algum comando já tratado, ou é só
        # um agrupamento) -- converte o conteúdo normalmente
        # -------------------------
        if c == "{":
            conteudo, i = _extrair_argumento(expr, i)
            resultado.append(_latex_para_fala(conteudo))
            continue

        # -------------------------
        # Operadores básicos
        # -------------------------
        if c == "+":
            resultado.append("mais")
            i += 1
            continue

        if c == "-":
            resultado.append("menos")
            i += 1
            continue

        if c == "=":
            resultado.append("igual a")
            i += 1
            continue

        if c == "*":
            resultado.append("vezes")
            i += 1
            continue

        if c == "/":
            resultado.append("sobre")
            i += 1
            continue

        # -------------------------
        # Chamada de função: f(x), f(x+1), sin(x)...
        # -------------------------
        if c == "(":
            fim = _encontrar_fechamento(expr, i, "(", ")")
            conteudo = expr[i + 1:fim]
            resultado.append("de " + _latex_para_fala(conteudo))
            i = fim + 1
            continue

        if c in ")]":
            i += 1
            continue

        if c == "[":
            i += 1
            continue

        # -------------------------
        # Números
        # -------------------------
        if c.isdigit():
            j = i

            while j < n and expr[j].isdigit():
                j += 1

            resultado.append(_numero_por_extenso(expr[i:j]))
            i = j
            continue

        # -------------------------
        # Aspa simples solta (derivada f'(x) sem ter sido pega junto com
        # a letra, ex.: expressão começando direto com ')
        # -------------------------
        if c == "'":
            resultado.append("linha")
            i += 1
            continue

        # -------------------------
        # Letras: nomes de função conhecidos (sin, cos, log...), notação
        # de derivada f'(x), ou variável solta (x, y, n, a, b...)
        # -------------------------
        if c.isalpha():
            j = i

            while j < n and expr[j].isalpha():
                j += 1

            token = expr[i:j]
            i = j

            if token.lower() in FUNCOES_CONHECIDAS:
                token_falado = FUNCOES_CONHECIDAS[token.lower()]
            elif len(token) > 1:
                # nome de variável com mais de uma letra e não reconhecido:
                # melhor soletrar do que arriscar o Edge-TTS ler como uma
                # palavra qualquer em português
                token_falado = " ".join(list(token))
            else:
                token_falado = token

            # f'(x) -> "derivada de f" (o "(x)" vira "de x" pelo
            # tratamento normal de chamada de função logo em seguida)
            if i < n and expr[i] == "'":
                i += 1
                resultado.append(f"derivada de {token_falado}")
            else:
                resultado.append(token_falado)

            continue

        # Qualquer outro caractere não mapeado é ignorado (em vez de
        # arriscar mandar símbolo estranho pro TTS)
        i += 1

    return re.sub(r"\s+", " ", " ".join(resultado)).strip()


def mathjax_para_fala(texto):
    """Substitui, dentro de `texto`, cada fórmula MathJax/LaTeX do Anki
    (\\( ... \\), \\[ ... \\], [$] ... [/$] ou [$$] ... [/$$]) pela sua
    versão falável em português, mantendo intacto todo o texto que está
    fora das fórmulas.

    Esta função NÃO altera nada em note["fields"]; ela só é chamada em
    cima da string local que será enviada ao TTS (ver loop principal).
    """

    def _substituir(match):
        conteudo = next(g for g in match.groups() if g is not None)

        try:
            falado = _latex_para_fala(conteudo)
            return falado if falado.strip() else " "

        except Exception:
            # Fallback defensivo: se por algum motivo a conversão
            # detalhada falhar numa fórmula fora do padrão, não trava o
            # script -- só remove os comandos LaTeX e as chaves, mantendo
            # letras, números e o texto legível o quanto der.
            fallback = re.sub(r"\\[a-zA-Z]+", " ", conteudo)
            fallback = fallback.replace("{", " ").replace("}", " ")
            fallback = fallback.replace("\\", " ")
            return re.sub(r"\s+", " ", fallback).strip()

    return MATHJAX_REGEX.sub(_substituir, texto)

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

        if tentativa < MAX_RETRIES:
            await asyncio.sleep(1 * tentativa)

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

        # Se o segmento não tem nenhuma letra/número falável (ex.: sobrou
        # só um "." ou "," depois de remover o cloze), o edge-tts falha
        # com "NoAudioReceived". Trata como se fosse vazio e pula.
        if not re.search(r"[\wÀ-ÿ]", texto_segmento):
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

            if tentativa < MAX_RETRIES:
                await asyncio.sleep(1 * tentativa)

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
# MENU INICIAL
# =========================

config = carregar_config()

print("\n" + "=" * 60)
print("ANKI TTS")
print("=" * 60)

print("""
1 - Gerar áudios
2 - Configurar tipos de nota / campos (adicionar, editar ou remover)
""")

opcao_inicial = input("Escolha: ").strip()

if opcao_inicial == "2":

    tipos_disponiveis = invoke("modelNames").get("result") or []

    if not tipos_disponiveis:
        print("Não foi possível listar os tipos de nota do Anki (AnkiConnect está aberto?).")
        exit()

    print("\nTipos de nota disponíveis no Anki:")
    model_name = escolher_da_lista(tipos_disponiveis, "Qual tipo de nota deseja configurar? ")

    if model_name:
        configurar_note_type_interativamente(model_name, config)

    print("\nConfiguração salva. Rode o script novamente para gerar os áudios.")
    exit()

elif opcao_inicial != "1":
    print("Opção inválida.")
    exit()

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
# AGRUPAR POR TIPO DE NOTA E ESCOLHER CAMPOS
# =========================
#
# Para cada tipo de nota encontrado entre as notas marcadas, este bloco:
# 1. Garante que existe uma configuração (perguntando na hora, se não
#    houver nenhuma ainda, com os campos reais lidos do Anki).
# 2. Mostra os campos já configurados como um menu numerado
#    (1.(campo1), 2.(campo2), n.(campoN)) e deixa escolher quais gerar
#    agora, sem precisar editar nada no código.

notas_por_modelo = {}

for note in infos:
    notas_por_modelo.setdefault(note["modelName"], []).append(note)

campos_por_modelo = {}
infos_processaveis = []

for model_name, notas in notas_por_modelo.items():

    if model_name not in config or not config[model_name].get("campos"):

        print(f"\nTipo de nota '{model_name}' ainda não tem campos de áudio configurados.")

        if input("Deseja configurar agora? (s/n): ").strip().lower() == "s":
            configurar_note_type_interativamente(model_name, config)
        else:
            print(f"Ignorando {len(notas)} nota(s) do tipo '{model_name}'.")
            continue

    campos_config = config.get(model_name, {}).get("campos", [])

    if not campos_config:
        print(f"Tipo de nota '{model_name}' sem campos configurados. Ignorando {len(notas)} nota(s).")
        continue

    amostra_fields = notas[0]["fields"]

    campos_escolhidos = escolher_campos_para_gerar(model_name, campos_config, amostra_fields)

    if not campos_escolhidos:
        print(f"Nenhum campo válido/selecionado para '{model_name}'. Ignorando {len(notas)} nota(s).")
        continue

    # Garante que os campos de destino existem de fato no tipo de nota
    # no Anki (cria automaticamente se faltar).
    campos_validos = [
        campo for campo in campos_escolhidos
        if garantir_campo_no_modelo(model_name, campo["destino"])
    ]

    if not campos_validos:
        print(f"Nenhum campo de destino pôde ser criado para '{model_name}'. Ignorando {len(notas)} nota(s).")
        continue

    campos_por_modelo[model_name] = campos_validos
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

    campos = campos_por_modelo[note["modelName"]]

    for campo in campos:

        campo_destino = campo["destino"]

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
    campos = campos_por_modelo[model_name]

    print("=" * 60)
    print(f"[{i}/{TOTAL}] ({model_name})")

    for campo in campos:

        campo_destino = campo["destino"]
        papel = campo["papel"]

        # -------------------------
        # MONTAR O TEXTO A SER FALADO
        # -------------------------

        if papel == "normal":

            campo_origem = campo["origem"]

            if campo_origem not in note["fields"]:
                print(f"Sem campo '{campo_origem}'")
                continue

            # Pipeline: texto original -> MathJax/LaTeX para fala ->
            # limpeza de HTML/etc -> Edge-TTS. Isso só afeta a string
            # local usada no áudio; note["fields"] nunca é alterado aqui.
            texto = limpar_texto(mathjax_para_fala(note["fields"][campo_origem]["value"]))

            segmentos = [("texto", texto)]

        elif papel == "cloze_pergunta":

            campo_texto = campo["origem"]

            if campo_texto not in note["fields"]:
                print(f"Sem campo '{campo_texto}'")
                continue

            # Converte MathJax/LaTeX -> fala ANTES de separar os
            # marcadores {{cN::...}}: assim, fórmulas tanto fora quanto
            # dentro de um cloze (ex.: {{c1::\(x^2\)}}) já chegam
            # convertidas em texto falável quando o cloze for
            # extraído/removido logo abaixo.
            valor_texto = mathjax_para_fala(note["fields"][campo_texto]["value"])

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

        elif papel == "cloze_resposta":

            campo_texto = campo["origem"]

            if campo_texto not in note["fields"]:
                print(f"Sem campo '{campo_texto}'")
                continue

            valor_texto = mathjax_para_fala(note["fields"][campo_texto]["value"])

            # Lê o conteúdo que estava escondido em {{cN::conteudo}},
            # limpando cada trecho (remove tags HTML etc.) antes de juntar
            respostas = extrair_respostas_cloze(valor_texto)
            respostas_limpas = [limpar_texto(r) for r in respostas]
            texto_respostas = ", ".join([r for r in respostas_limpas if r])

            # E soma o que estiver digitado manualmente no campo extra
            # (configurável, ex.: "Extra"), se houver um configurado
            texto_extra = ""
            campo_extra = campo.get("extra_origem")

            if campo_extra and campo_extra in note["fields"]:
                valor_extra = note["fields"][campo_extra]["value"]
                texto_extra = limpar_texto(mathjax_para_fala(valor_extra))

            partes = [p for p in [texto_respostas, texto_extra] if p]
            texto = ". ".join(partes)

            segmentos = [("texto", texto)]

        else:
            print(f"Papel de campo desconhecido: {papel}")
            continue

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

        print(f"\nGerando '{campo_destino}' (a partir de '{campo.get('origem')}')...")
        print(f"Texto: {texto[:80]}")

        if papel == "normal":

            # Sem pausas de cloze -> gera direto com o Edge-TTS, sem
            # passar pelo pydub (evita perda de qualidade por
            # recompressão do MP3).
            sucesso, erro = asyncio.run(
                gerar_audio_unico(
                    texto,
                    caminho_audio
                )
            )

        else:

            # cloze_pergunta / cloze_resposta: precisa juntar segmentos
            # de fala (e, no caso da pergunta, pausas reais de
            # silêncio) -> só aqui é necessário usar o pydub.
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