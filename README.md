# King Voice (IPix) - Python Async Wrapper

Wrapper assíncrono para consumo da API v2 do IPix (King Voice). Gerencia automaticamente o ciclo de vida do token JWT, retentativas de conexão (Rate Limit/5xx) e validação de payloads via Pydantic.

## ⚙️ Instalação e Configuração

1. **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure o ambiente local:**
    ```bash
    cp .env.example .env
    ```

    Estrutura esperada no `.env`:
    ```bash
    IPIX_ENDERECO=seu_ip
    IPIX_LOGIN=seu_usuario
    IPIX_SENHA=sua_senha
    ```


## 💻 Como Utilizar
O client deve ser instanciado sempre dentro de um gerenciador de contexto (`async with`) para garantir a gestão correta das sessões HTTP.

O script `main.py` incluído neste projeto demonstra a implementação prática: ele extrai as credenciais do arquivo `.env`, executa a autenticação automática e consome o módulo de relatórios para buscar todas as chamadas abandonadas dos últimos 7 dias.


## 📦 Módulos Disponíveis
Todos os endpoints da API v2 estão mapeados e acessíveis via `client.<modulo>`:

* `autenticacao` (Login e refresh de tokens)
* `relatorios` (Atendidas, Abandonadas, Totalizador, Nível de Serviço, etc.)
* `ramais` (CRUD e Status)
* `agentes` (Login/Logout)
* `chamadas` (Realizar chamadas API/Web)
* `pausas`
* `pesquisas`
* Outros: `agenda`, `conferencias`, `dnd`, `filas`, `historico`, `pausas`, `pesquisas`, `sms`, `status`, `usuarios`.

**Nota sobre Certificados:** A verificação SSL está desativada nativamente (`verify=False`) para compatibilidade imediata com ambientes locais da King Voice.