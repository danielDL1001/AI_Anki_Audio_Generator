# Imagem base com Python (3.11: compatível com o pydub sem ajustes)
FROM python:3.11-slim
 
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
 
# Define o diretório de trabalho dentro do container
WORKDIR /app
 
# ffmpeg é obrigatório: o pydub o usa para montar os áudios dos cards Cloze
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
 
# Instala as dependências Python (camada separada para aproveitar o cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Copia os arquivos do projeto
COPY . .
 
# O script é interativo: rode com
#   docker compose run --rm anki-audio-generator
CMD ["python", "main.py"]
 
