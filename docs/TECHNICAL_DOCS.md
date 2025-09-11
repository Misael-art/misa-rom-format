# Documentação Técnica do Formato .misa

Este documento aprofunda os aspectos técnicos do formato `.misa`, incluindo a API de leitura, truques de otimização e um guia de troubleshooting.

## 1. API de Leitura de Arquivos .misa (`misa_read`)

A API `misa_read` é a interface principal para acessar dados de ROMs dentro de arquivos `.misa`. Ela é projetada para ser eficiente e permitir acesso aleatório (seek) aos dados, descompactando apenas os chunks necessários.

### 1.1. Função `misa_read_seek(file_handle, offset, whence)`

Permite posicionar o ponteiro de leitura dentro do fluxo de dados da ROM virtual.

**Parâmetros:**

*   `file_handle`: Um identificador para o arquivo `.misa` aberto.
*   `offset` (int): O deslocamento em bytes a partir do qual a leitura deve começar.
*   `whence` (int): O ponto de referência para o `offset`.
    *   `0` (ou `SEEK_SET`): Início do arquivo.
    *   `1` (ou `SEEK_CUR`): Posição atual do ponteiro.
    *   `2` (ou `SEEK_END`): Fim do arquivo.

**Retorna:**
A nova posição do ponteiro de leitura.

**Comportamento:**
Quando um `seek` é realizado para uma posição dentro de um chunk comprimido, a API `misa_read` identifica o chunk correspondente, descompacta-o (se ainda não estiver em cache) e posiciona o ponteiro de leitura no `offset` desejado dentro do chunk descompactado.

### 1.2. Função `misa_read_data(file_handle, size)`

Lê uma quantidade específica de bytes a partir da posição atual do ponteiro.

**Parâmetros:**

*   `file_handle`: Um identificador para o arquivo `.misa` aberto.
*   `size` (int): O número de bytes a serem lidos.

**Retorna:**
Os dados lidos (bytes).

## 2. Truques de Otimização e Implementação

### 2.1. Dicionários Treinados (`assets/`)

Para coders que utilizam compressão baseada em dicionário (ex: Zstd), dicionários pré-treinados são armazenados no diretório `assets/`. Esses dicionários são gerados a partir de grandes coleções de ROMs de consoles específicos, otimizando a taxa de compressão para jogos daquele sistema.

*   **Geração**: Os dicionários são gerados usando um subconjunto representativo de ROMs de um console.
*   **Uso**: Durante a compressão, o coder selecionado carrega o dicionário apropriado para o console de destino. Durante a descompressão, o mesmo dicionário é usado.

### 2.2. Δ-LUT (Delta Look-Up Table) para N64

O coder `Delta-LUT` é uma otimização específica para ROMs de Nintendo 64 (e potencialmente outros sistemas com padrões de dados semelhantes, como PS1). Ele explora a natureza repetitiva de certos dados em ROMs, como texturas e dados de áudio, armazenando diferenças (deltas) em vez dos dados completos.

*   **Princípio**: Em vez de comprimir blocos de dados diretamente, o `Delta-LUT` compara blocos com uma tabela de referência (LUT) e armazena apenas a diferença, que é significativamente menor.
*   **Benefícios**: Redução substancial no tamanho do arquivo para ROMs com alta redundância, como as de N64.

## 3. Troubleshooting

Esta seção aborda problemas comuns e suas soluções.

### 3.1. Erros de Coder

**Problema:** A compressão ou descompressão falha com um erro relacionado a um coder específico.

**Causas Comuns:**

*   **Coder não encontrado:** O `coder_id` especificado não existe ou não está registrado.
*   **Dados corrompidos:** O chunk de dados comprimidos está corrompido, impedindo a descompressão.
*   **Dicionário ausente/inválido:** Para coders baseados em dicionário, o arquivo de dicionário correspondente está faltando ou foi corrompido.

**Soluções:**

*   **Verifique o `coder_id`:** Certifique-se de que o `coder_id` usado é válido e corresponde a um coder implementado.
*   **Verificação de Integridade (CRC):** O formato `.misa` inclui CRCs para cada chunk. Use a ferramenta `misa dump` para verificar a integridade dos chunks. Se um chunk estiver corrompido, a ROM original pode precisar ser re-comprimida.
*   **Reinstale/Verifique Dicionários:** Para problemas de dicionário, tente reinstalar a ferramenta `misa` ou verificar a integridade dos arquivos em `assets/`.

### 3.2. Cálculo de Overhead

**Problema:** O overhead reportado é maior do que o esperado (<0.1%).

**Causas Comuns:**

*   **ROMs muito pequenas:** Para ROMs extremamente pequenas, o cabeçalho de 128 bytes e a estrutura de chunks podem representar uma porcentagem maior do tamanho total, aumentando o overhead percebido.
*   **Coders ineficientes:** O coder selecionado pode não ser o mais eficiente para o tipo de dados da ROM específica.
*   **Metadados excessivos:** Embora a `misa_meta` seja pequena, metadados adicionais não otimizados podem contribuir para o overhead.

**Soluções:**

*   **Considere o tamanho da ROM:** O overhead é mais relevante para ROMs de tamanho médio a grande. Para ROMs muito pequenas, o benefício da compressão pode ser marginal.
*   **Experimente diferentes coders:** Use o comando `misa compress` com diferentes opções de `--coder` para encontrar o mais eficiente para sua ROM.
*   **Analise a estrutura .misa:** Use `misa dump --json` para inspecionar a estrutura interna e identificar onde o espaço está sendo utilizado.