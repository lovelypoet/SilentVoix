import asyncio
import os
import pygame
from tts_service import tts_service

async def main():
    result = await tts_service.speak("fuck you do your job, what a fucking dumbass. If you dont work i swear i will slap your dirty ass")
    if result["status"] == "success":
        abs_path = os.path.abspath(result["audio_path"])
        print(f"Audio file generated at: {abs_path}")

        # Initialize and play with pygame
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.music.load(abs_path)
        pygame.mixer.music.play()

        # Keep the script alive until audio is done playing
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    else:
        print("TTS failed:", result)

if __name__ == "__main__":
    asyncio.run(main())
