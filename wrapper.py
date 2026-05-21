import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

class APIException(Exception):
    pass

class RateLimitException(APIException):
    pass

class ServerException(APIException):
    pass

class UnauthorizedException(APIException):
    pass

class LoginRequest(BaseModel):
    login: str
    senha: str

class LoginResponse(BaseModel):
    token: str
    mensagem: str

class AgendaContato(BaseModel):
    idAgenda: str
    nome: str
    empresa: str
    telefone1: str
    telefone2: str
    telefone3: str
    tipo: str
    idUsuario: str
    codigo_discagem_rapida: str

class AgendaCreate(BaseModel):
    nome: str
    empresa: str
    telefone1: str
    telefone2: str
    telefone3: str
    tipo: str
    idUsuario: str
    codigo_discagem_rapida: str

class AgendaUpdate(AgendaCreate):
    idAgenda: str

class AgenteAuth(BaseModel):
    id_usuario: str
    senha: str
    ramal: str

class ChamadaRequest(BaseModel):
    loginDinamico: bool
    origem: str
    destino: str
    reversa: bool
    custom_app: bool
    retiraDDD: bool

class ChamadaWebRequest(BaseModel):
    destino1: str
    destino2: str
    contexto: str

class Conferencia(BaseModel):
    sala: str
    nome: str

class SMSRequest(BaseModel):
    destino: List[str]
    mensagem: str = Field(..., max_length=150)
    configuracao: str

class Fila(BaseModel):
    sala: str
    nome: str

class PausaRequest(BaseModel):
    loginDinamico: bool
    origem: str
    codigo: str
    filas: str

class RamalCreate(BaseModel):
    numero_ramal: str
    nome_ramal: str
    senha: str
    gravacoes_habilitadas: bool
    voicemail_habilitado: bool
    voicemail_email: str
    tipo_atendeaki: bool
    tipo_normal: bool
    sigame_habilitado: bool
    sigame_ramais: str
    destino_ocupado: str
    destino_sem_resposta: str
    destino_indisponivel: str
    tag: str

class RamalUpdate(BaseModel):
    nome_ramal: str
    senha: str
    gravacoes_habilitadas: bool
    voicemail_habilitado: bool
    voicemail_email: str
    tipo_atendeaki: bool
    tipo_normal: bool
    sigame_habilitado: bool
    sigame_ramais: str
    destino_ocupado: str
    destino_sem_resposta: str
    destino_indisponivel: str
    tag: str

class StatusRamalRequest(BaseModel):
    status: str
    mensagem: str

class HTTPClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        headers = {"Content-Type": "application/json"}
        self.client = httpx.AsyncClient(base_url=self.base_url, verify=False, headers=headers)
        self._token: Optional[str] = None
        self.auth_payload: Optional[Dict[str, str]] = None

    @property
    def token(self) -> Optional[str]:
        return self._token
    
    @token.setter
    def token(self, value: str) -> None:
        self._token = value
        if value:
            self.client.headers["Authorization"] = f"Bearer {value}"
            self.client.headers["token"] = value

    async def close(self) -> None:
        await self.client.aclose()

    def set_auth_data(self, payload: Dict[str, str]) -> None:
        self.auth_payload = payload

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((RateLimitException, ServerException)),
        reraise=True,
    )
    async def _execute_request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        response = await self.client.request(method, endpoint, **kwargs)

        if response.status_code == 429:
            logger.warning("Rate limit exceeded for %s", endpoint)
            raise RateLimitException()
        if response.status_code >= 500:
            logger.error("Server error on %s", endpoint)
            raise ServerException()

        return response

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        response = await self._execute_request(method, endpoint, **kwargs)

        if response.status_code == 401 and self.auth_payload:
            await self._refresh_token()
            response = await self._execute_request(method, endpoint, **kwargs)

        response.raise_for_status()

        if response.status_code != 204 and response.text:
            return response.json()
        return {}

    async def _refresh_token(self) -> None:
        if not self.auth_payload:
            raise UnauthorizedException()
        response = await self.client.post("/login", json=self.auth_payload)
        response.raise_for_status()
        self.token = response.json().get("token")

class AuthModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def login(self, credentials: LoginRequest) -> LoginResponse:
        self.http.set_auth_data(credentials.model_dump())
        data = await self.http.request("POST", "/login", json=credentials.model_dump())
        response_data = LoginResponse(**data)
        self.http.token = response_data.token
        return response_data

class AgendaModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self, **params: Any) -> Dict[str, Any]:
        return await self.http.request("GET", "/agenda", params=params)

    async def criar(self, contato: AgendaCreate) -> Dict[str, Any]:
        return await self.http.request("POST", "/agenda", json=contato.model_dump())

    async def atualizar(self, contato: AgendaUpdate) -> Dict[str, Any]:
        return await self.http.request("PUT", "/agenda", json=contato.model_dump())

    async def deletar(self, id_agenda: str) -> Dict[str, Any]:
        return await self.http.request("DELETE", f"/agenda/{id_agenda}")

class AgentesModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def login(self, agente: AgenteAuth) -> Dict[str, Any]:
        return await self.http.request("POST", "/agentes_login", json=agente.model_dump())

    async def logout(self, agente: AgenteAuth) -> Dict[str, Any]:
        return await self.http.request("DELETE", "/agentes_login", params=agente.model_dump())

class ChamadasModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def realizar_chamada(self, chamada: ChamadaRequest) -> Dict[str, Any]:
        return await self.http.request("POST", "/chamada", json=chamada.model_dump())

    async def realizar_chamada_web(self, chamada: ChamadaWebRequest) -> Dict[str, Any]:
        return await self.http.request("POST", "/chamadaweb", json=chamada.model_dump())

class ConferenciasModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self) -> List[Conferencia]:
        data = await self.http.request("GET", "/conferencias")
        return [Conferencia(**item) for item in data]

    async def obter(self, sala: str) -> Dict[str, Any]:
        return await self.http.request("GET", f"/conferencias/{sala}")

class DNDModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def ativar(self, ramal: str) -> Dict[str, Any]:
        return await self.http.request("POST", f"/dnd/{ramal}")

    async def desativar(self, ramal: str) -> Dict[str, Any]:
        return await self.http.request("DELETE", f"/dnd/{ramal}")

class FilasModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self) -> List[Fila]:
        data = await self.http.request("GET", "/filas")
        return [Fila(**item) for item in data]

class HistoricoModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def buscar(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({
            "dataInicial": data_inicial.replace(microsecond=0).isoformat(),
            "dataFinal": data_final.replace(microsecond=0).isoformat()
        })
        return await self.http.request("GET", "/historico", params=params)

class PausasModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def pausar(self, pausa: PausaRequest) -> Dict[str, Any]:
        return await self.http.request("POST", "/pausa", json=pausa.model_dump())

    async def listar(self, ativas: bool) -> Dict[str, Any]:
        return await self.http.request("GET", "/pausas", params={"ativas": ativas})

class PesquisasModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self, ativas: Optional[int] = None) -> Dict[str, Any]:
        params = {"ativas": ativas} if ativas is not None else {}
        return await self.http.request("GET", "/pesquisas_satisfacao", params=params)

class RamaisModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self, **params: Any) -> Dict[str, Any]:
        return await self.http.request("GET", "/ramais", params=params)

    async def criar(self, ramal: RamalCreate) -> Dict[str, Any]:
        return await self.http.request("POST", "/ramais", json=ramal.model_dump())

    async def obter(self, numero_ramal: str) -> Dict[str, Any]:
        return await self.http.request("GET", f"/ramais/{numero_ramal}")

    async def atualizar(self, numero_ramal: str, ramal: RamalUpdate) -> Dict[str, Any]:
        return await self.http.request("PUT", f"/ramais/{numero_ramal}", json=ramal.model_dump())

    async def deletar(self, numero_ramal: str) -> Dict[str, Any]:
        return await self.http.request("DELETE", f"/ramais/{numero_ramal}")

    async def alterar_status(self, numero_ramal: str, status: StatusRamalRequest) -> Dict[str, Any]:
        return await self.http.request("POST", f"/ramais/{numero_ramal}/status", json=status.model_dump())

class SMSModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def enviar(self, sms: SMSRequest) -> Dict[str, Any]:
        return await self.http.request("POST", "/enviosms", json=sms.model_dump())

class StatusModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self) -> List[str]:
        return await self.http.request("GET", "/status")

class UsuariosModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def listar(self, **params: Any) -> Dict[str, Any]:
        return await self.http.request("GET", "/usuarios", params=params)

    async def upload_avatar(self, id_usuario: str, arquivo_path: str) -> Dict[str, Any]:
        with open(arquivo_path, "rb") as f:
            arquivos = {"avatar": f}
            return await self.http.request("POST", f"/usuarios/{id_usuario}/avatar", files=arquivos)

class RelatoriosModule:
    def __init__(self, http_client: HTTPClient):
        self.http = http_client

    async def chamadas_abandonadas(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/abandonadas/relatorio", params=params)

    async def agentes(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/agentes/relatorio", params=params)

    async def chamadas_atendidas(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/atendidas/relatorio", params=params)

    async def distribuicao_chamadas(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/distribuicao_chamadas/relatorio", params=params)

    async def estatistica_fila(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/estatistica_fila/relatorio", params=params)

    async def estatistica_detalhada(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/estatistica_detalhada/relatorio", params=params)

    async def nivel_servico(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/nivel_servico/relatorio", params=params)

    async def pausas(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/pausas/relatorio", params=params)

    async def pesquisas(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/pesquisas/relatorio", params=params)

    async def totalizador(self, data_inicial: datetime, data_final: datetime, **params: Any) -> Dict[str, Any]:
        params.update({"dataInicial": data_inicial.replace(microsecond=0).isoformat(), "dataFinal": data_final.replace(microsecond=0).isoformat()})
        return await self.http.request("GET", "/totalizador/relatorio", params=params)

class KingVoiceClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self._http_client = HTTPClient(base_url)

        if token:
            self._http_client.token = token
        
        self.autenticacao = AuthModule(self._http_client)
        self.agenda = AgendaModule(self._http_client)
        self.agentes = AgentesModule(self._http_client)
        self.chamadas = ChamadasModule(self._http_client)
        self.conferencias = ConferenciasModule(self._http_client)
        self.dnd = DNDModule(self._http_client)
        self.filas = FilasModule(self._http_client)
        self.historico = HistoricoModule(self._http_client)
        self.pausas = PausasModule(self._http_client)
        self.pesquisas = PesquisasModule(self._http_client)
        self.ramais = RamaisModule(self._http_client)
        self.sms = SMSModule(self._http_client)
        self.status = StatusModule(self._http_client)
        self.usuarios = UsuariosModule(self._http_client)
        self.relatorios = RelatoriosModule(self._http_client)

    async def __aenter__(self) -> "KingVoiceClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._http_client.close()