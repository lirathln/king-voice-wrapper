import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
import httpx

from wrapper import KingVoiceClient, LoginRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def load_settings() -> tuple[str, str, str]:
    load_dotenv()
    
    api_url = os.getenv("IPIX_ENDERECO")
    username = os.getenv("IPIX_LOGIN")
    password = os.getenv("IPIX_SENHA")
    
    if not all([api_url, username, password]):
        logging.error("Configuration aborted: Missing required environment variables (IPIX_URL, IPIX_LOGIN, IPIX_SENHA).")
        sys.exit(1)
        
    return api_url, username, password

async def main():
    api_url, username, password = load_settings()
    
    current_date = datetime.now().replace(microsecond=0)
    start_date = current_date - timedelta(days=7)

    async with KingVoiceClient(base_url=f"https://{api_url}/ipix-gestao/api/v2") as client:
        try:
            auth_data = LoginRequest(login=username, senha=password)
            await client.autenticacao.login(auth_data)
            logging.info("Authentication successful.")

            # Parâmetros kwargs (data_inicial, data_final) seguem o padrão do IPix
            abandoned_calls_report = await client.relatorios.chamadas_abandonadas(
                data_inicial=start_date,
                data_final=current_date
            )
            
            results = abandoned_calls_report.get("resultados", [])
            logging.info(f"Abandoned calls report processed. Total records: {len(results)}")

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP Error {e.response.status_code} at URL {e.request.url}")
            logging.error(f"Server details: {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected execution failure: {e}")

if __name__ == "__main__":
    asyncio.run(main())