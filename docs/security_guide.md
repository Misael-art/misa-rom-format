# Guia de Segurança

Este documento detalha as práticas de segurança implementadas no projeto Mega_Emu_DataBase_ROMs para proteger dados e prevenir vulnerabilidades.

## Prepared Statements: Prevenção de Injeção SQL

A injeção SQL é uma das vulnerabilidades mais comuns em aplicações que interagem com bancos de dados. No Mega_Emu_DataBase_ROMs, utilizamos **Prepared Statements** para mitigar esse risco, garantindo que todas as entradas do usuário sejam tratadas como dados, e não como parte da lógica SQL.

**Como funciona:**

Em vez de concatenar strings para construir queries SQL, os Prepared Statements usam placeholders para os valores que serão inseridos. O banco de dados então "prepara" a query (compila-a) uma vez, e os valores são passados separadamente, sem serem interpretados como código SQL.

**Exemplo de Código (Python com `sqlite3`):**

**❌ Evite (Vulnerável à Injeção SQL):**

```python
# NUNCA FAÇA ISSO!
user_input = "'; DROP TABLE roms; --"
query = f"SELECT * FROM roms WHERE name = '{user_input}'"
cursor.execute(query)
```

Neste exemplo, se `user_input` contiver código SQL malicioso, ele será executado.

**✅ Use (Seguro com Prepared Statements):**

```python
import sqlite3

def get_roms_by_name(db_path: str, rom_name: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # O placeholder '?' garante que rom_name seja tratado como dado
    query = "SELECT * FROM roms WHERE name = ?"
    cursor.execute(query, (rom_name,))
    roms = cursor.fetchall()
    conn.close()
    return roms

# Exemplo de uso
db_file = "data/default.db"
search_name = "Mega Man X"
found_roms = get_roms_by_name(db_file, search_name)
```

Aqui, `rom_name` é passado como um parâmetro separado para `cursor.execute()`, prevenindo qualquer tentativa de injeção SQL.

## Mascaramento de Logs com `SecureFormatter`

A exposição de dados sensíveis em logs pode ser uma grave falha de segurança. O projeto utiliza um `SecureFormatter` personalizado para mascarar automaticamente informações confidenciais, como caminhos de arquivos, hashes de ROMs e senhas (se aplicável), antes que sejam gravadas nos arquivos de log.

**Como funciona:**

O `SecureFormatter` emprega expressões regulares (regex) para identificar padrões de dados sensíveis dentro das mensagens de log. Uma vez identificado, o dado é substituído por um valor mascarado (ex: `[MASCARADO]`, `****`) ou por uma versão truncada e ofuscada.

**Exemplo de Configuração (Conceitual):**

```python
import logging
import re

class SecureFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.patterns = {
            # Regex para caminhos de arquivo (ex: C:\Users\...)
            "file_path": re.compile(r"(?:[a-zA-Z]:\\|\/)?(?:[\w\s\-\._]+\\?|\/?)+[\w\s\-\._]+\.(rom|zip|7z|iso|bin)", re.IGNORECASE),
            # Regex para hashes SHA1, MD5, CRC32
            "hash": re.compile(r"\b([a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{8})\b", re.IGNORECASE),
            # Adicionar outros padrões conforme necessário (ex: senhas, chaves API)
        }

    def format(self, record):
        message = super().format(record)
        for key, pattern in self.patterns.items():
            if key == "file_path":
                message = pattern.sub("[CAMINHO_MASCARADO]", message)
            elif key == "hash":
                message = pattern.sub("[HASH_MASCARADO]", message)
            # Adicionar lógica de mascaramento para outros tipos
        return message

# Exemplo de uso (configuração do logger)
# logger = logging.getLogger(__name__)
# handler = logging.FileHandler("secure.log")
# handler.setFormatter(SecureFormatter('%(asctime)s - %(levelname)s - %(message)s'))
# logger.addHandler(handler)
# logger.warning("ROM path: C:\\Users\\User\\Games\\rom.zip, SHA1: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0")
# Saída no log: ROM path: [CAMINHO_MASCARADO], SHA1: [HASH_MASCARADO]
```

Este mecanismo garante que, mesmo em caso de acesso não autorizado aos logs, informações críticas não sejam diretamente expostas.

## Melhores Práticas de Segurança

Além das medidas acima, o projeto adere a várias melhores práticas para garantir a segurança e robustez:

*   **Validação de ROM Paths:** Todos os caminhos de ROMs são validados rigorosamente para prevenir ataques de travessia de diretório (directory traversal) e garantir que os arquivos acessados estejam dentro dos diretórios esperados.
*   **Mascaramento de Hashes:** Hashes de ROMs (CRC32, MD5, SHA1) são tratados como dados sensíveis e mascarados em logs para evitar que sejam usados em ataques de engenharia reversa ou para identificar ROMs específicas.
*   **Uso de `constants.py` para Timeouts e Configurações:** Valores críticos como timeouts de rede, limites de pool de conexões e outras configurações de segurança são centralizados em `constants.py`. Isso evita "hardcoding" e facilita a auditoria e atualização de parâmetros de segurança.
*   **Tratamento de Exceções Robusto:** O sistema implementa tratamento de exceções abrangente para capturar e lidar com erros de forma segura, evitando a exposição de detalhes internos do sistema a usuários mal-intencionados.
*   **Princípio do Menor Privilégio:** As operações de banco de dados e sistema são executadas com o menor privilégio necessário para sua função, minimizando o impacto de uma possível exploração.

## Diagrama de Fluxo de Segurança (Query Segura)

Este diagrama ilustra o fluxo de uma query segura no sistema, desde a entrada do usuário até a execução no banco de dados.

```mermaid
graph TD
    A[Entrada do Usuário] --> B{Validação de Entrada};
    B -- Dados Válidos --> C[Preparar Statement (Placeholders)];
    C --> D[Executar Query com Parâmetros];
    D --> E[Banco de Dados SQLite];
    E -- Resultados --> F[Processar Resultados];
    F --> G[Exibir/Usar Dados];

    B -- Dados Inválidos --> H[Rejeitar Entrada / Erro];

    style A fill:#f9f,stroke:#333,stroke-width:2px;
    style B fill:#bbf,stroke:#333,stroke-width:2px;
    style C fill:#bbf,stroke:#333,stroke-width:2px;
    style D fill:#bbf,stroke:#333,stroke-width:2px;
    style E fill:#ccf,stroke:#333,stroke-width:2px;
    style F fill:#bbf,stroke:#333,stroke-width:2px;
    style G fill:#f9f,stroke:#333,stroke-width:2px;
    style H fill:#f00,stroke:#333,stroke-width:2px;