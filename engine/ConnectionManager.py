import aiohttp
import logging

log = logging.getLogger("jarvis.lm_manager")

class LMManager:
    def __init__(self, url="http://127.0.0.1:1234/v1"):
        self.url = url
        self.is_online = False

    async def check_connection(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.url}/models", timeout=2) as response:
                    self.is_online = response.status == 200
                    return self.is_online
        except Exception:
            self.is_online = False
            return False

lm_manager = LMManager()