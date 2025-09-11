# Guia do Usuário do Mega_Emu_DataBase_ROMs

Este guia fornece instruções detalhadas sobre como usar a ferramenta CLI `misa` e como integrar arquivos `.misa` com emuladores.

## 1. Usando a Ferramenta CLI `misa`

A ferramenta `misa` permite gerenciar e manipular seus arquivos `.misa`.

### 1.1. Instalação

Certifique-se de ter o Python 3.8+ instalado.

```bash
pip install megaemu-misa
```

### 1.2. Comandos Principais

#### `misa compress` - Comprimir ROMs para o formato .misa

Este comando converte uma ROM tradicional para o formato `.misa`, aplicando os coders de compressão otimizados.

**Uso:**
```bash
misa compress --input <caminho_para_rom> --output <caminho_para_misa> --console <nome_do_console> [--coder <coder_id>]
```

**Exemplos:**

*   **Comprimir uma ROM de PlayStation 2:**
    ```bash
    misa compress --input "C:/Roms/PS2/GodOfWar.iso" --output "D:/MisaRoms/GodOfWar.misa" --console ps2
    ```
    *Isso usará o coder padrão otimizado para PS2.*

*   **Comprimir uma ROM de N64 usando um coder específico (ex: Delta-LUT):**
    ```bash
    misa compress --input "C:/Roms/N64/ZeldaOoT.z64" --output "D:/MisaRoms/ZeldaOoT.misa" --console n64 --coder Delta-LUT
    ```

#### `misa decompress` - Descomprimir arquivos .misa

Este comando reverte um arquivo `.misa` para o formato original da ROM.

**Uso:**
```bash
misa decompress --input <caminho_para_misa> --output <caminho_para_rom_original>
```

**Exemplo:**
```bash
misa decompress --input "D:/MisaRoms/GodOfWar.misa" --output "C:/Roms/PS2/GodOfWar_original.iso"```

#### `misa dump` - Visualizar metadados e estrutura de um arquivo .misa

Permite inspecionar o cabeçalho e os metadados de um arquivo `.misa`.

**Uso:**
```bash
misa dump --input <caminho_para_misa> [--json]
```

**Exemplos:**

*   **Visualizar metadados em formato legível:**
    ```bash
    misa dump --input "D:/MisaRoms/ZeldaOoT.misa"
    ```
*   **Visualizar metadados em formato JSON para processamento programático:**
    ```bash
    misa dump --input "D:/MisaRoms/ZeldaOoT.misa" --json
    ```

#### `misa benchmark` - Executar benchmarks de desempenho

Avalia o desempenho de boot, seek e taxa de transferência de um arquivo `.misa`.

**Uso:**
```bash
misa benchmark --input <caminho_para_misa>
```

**Exemplo:**
```bash
misa benchmark --input "D:/MisaRoms/GodOfWar.misa"
```

## 2. Integração com Emuladores

O formato `.misa` é projetado para ser transparente para emuladores, mas a integração nativa pode ser alcançada através de pequenos patches ou plugins.

### 2.1. Patch para RetroArch (Exemplo)

Para integrar o `.misa` ao RetroArch, um patch de aproximadamente 50 linhas pode ser aplicado ao código-fonte do core do emulador. Este patch interceptaria as chamadas de leitura de arquivo e as redirecionaria para a API `misa_read`, que lida com a descompressão sob demanda.

**Exemplo de Pseudocódigo para Patch (C/C++):**

```c
// Dentro da função de carregamento de ROM do core do emulador
FILE *original_fopen(const char *path, const char *mode); // Ponteiro para a função fopen original

// Nossa função de abertura de arquivo customizada
FILE *misa_fopen(const char *path, const char *mode) {
    if (strstr(path, ".misa") != NULL) {
        // Se for um arquivo .misa, use nossa API de leitura
        return misa_api_open(path, mode); // Função da API .misa
    } else {
        // Caso contrário, use a função fopen original
        return original_fopen(path, mode);
    }
}

// No início do core, substituir fopen
// original_fopen = fopen;
// fopen = misa_fopen;
```

**Passos para Aplicação do Patch:**

1.  Obtenha o código-fonte do core do RetroArch desejado.
2.  Identifique a função de carregamento de ROM ou as chamadas de leitura de arquivo (ex: `fopen`, `fread`).
3.  Implemente a lógica de interceptação e redirecionamento para a API `misa_read`.
4.  Compile o core modificado.

### 2.2. Outros Emuladores

Para outros emuladores, a abordagem pode variar:

*   **Plugins**: Desenvolver um plugin que se integre ao sistema de arquivos do emulador.
*   **Modificações Diretas**: Aplicar patches semelhantes ao exemplo do RetroArch.
*   **Wrapper de Arquivos**: Criar um script ou ferramenta que descompacte o `.misa` para um arquivo temporário antes de iniciar o emulador.