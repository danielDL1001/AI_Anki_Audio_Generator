import asyncio
import edge_tts
import pygame
import tempfile
import os

texto = "Esse é um áudio teste em português brasileiro." # Texto teste para gerar o áudio

async def falar():
    # Cria arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        caminho = temp_audio.name

    # Gera voz
    communicate = edge_tts.Communicate(
        text=texto,
        voice="pt-BR-FranciscaNeural" # Aqui pode alterar para outra voz disponível
    )

    await communicate.save(caminho)

    # Inicializa player
    pygame.mixer.init()
    pygame.mixer.music.load(caminho)
    pygame.mixer.music.play()

    # Espera terminar
    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.1)

    # Remove arquivo temporário
    os.remove(caminho)

asyncio.run(falar())