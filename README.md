# MISAROM

O MISAROM é um MVP (Minimum Viable Product) em Python projetado para gerenciar e enriquecer dados de ROMs de emuladores, integrando funcionalidades de IA e banco de dados SQLite. O projeto é pronto para produção e foca em simplicidade e escalabilidade.

## Visão Geral

- **Módulo .misa**: Configurações do projeto armazenadas em `.misa/config.json`.
- **Módulo IA (ia/)**: Integração com serviços de IA via biblioteca Requests para enriquecimento de metadados.
- **Banco de Dados (db/)**: Setup inicial com SQLite para armazenamento persistente de dados.
- **Ponto de Entrada (main.py)**: Script principal com logging e tratamento de erros robusto.
- **Dependências (requirements.txt)**: Inclui Flask, Requests e sqlite3.

O projeto é estruturado para fácil manutenção e expansão futura.

## Instalação

1. Clone o repositório ou baixe os arquivos para um diretório local.
2. Certifique-se de ter Python 3.8+ instalado.
3. Instale as dependências:

   ```
   pip install -r requirements.txt
   ```

4. Configure o arquivo `.misa/config.json` com as chaves necessárias (ex: API de IA, se aplicável).
5. Execute o aplicativo:

   ```
   python main.py
   ```

## Uso Básico

- Inicie o servidor com `python main.py`.
- Acesse as rotas via Flask (ex: endpoints para upload de ROMs e enriquecimento via IA).
- Monitore logs para depuração.
- Para uso em produção, configure variáveis de ambiente para chaves sensíveis.

Exemplo de uso via curl (assumindo endpoint /enrich):

```
curl -X POST http://localhost:5000/enrich -F "rom=@sample.rom"
```

## Módulos Detalhados

- **.misa/config.json**: Armazena configurações como caminhos de DB e endpoints de IA.
- **ia/**: Módulo básico para chamadas HTTP a APIs de IA usando Requests.
- **db/**: Scripts para inicialização e migrações do SQLite.
- **main.py**: Inicializa o app Flask, configura logging e roteia requisições.

## Próximos Passos e Recursos

- Cobertura de testes futura superior a 90% com pytest.
- Expansão de funcionalidades de IA para análise multimodal.
- Suporte a múltiplos bancos de dados.
- Integração com GitHub Actions para CI/CD.

Para mais detalhes, consulte a pasta `docs/`.