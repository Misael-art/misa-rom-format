# Diretrizes para Docstrings e Comentários de Código

Este documento estabelece as diretrizes para a escrita de docstrings e comentários de código no projeto Mega_Emu_DataBase_ROMs, garantindo clareza, consistência e manutenibilidade.

## 1. Docstrings (Python)

Todas as funções, classes e módulos Python devem incluir docstrings. Utilizaremos o formato Google Style Docstrings.

### 1.1. Módulos

```python
"""
Módulo para manipulação de arquivos .misa e operações de compressão/descompressão.

Este módulo fornece funcionalidades para:
- Comprimir ROMs para o formato .misa.
- Descomprimir arquivos .misa para o formato original da ROM.
- Gerenciar diferentes coders de compressão.
"""
```

### 1.2. Classes

```python
class MisaFile:
    """
    Representa um arquivo .misa, fornecendo métodos para leitura e escrita.

    Atributos:
        path (str): O caminho para o arquivo .misa.
        header (MisaHeader): O cabeçalho do arquivo .misa.
    """
    def __init__(self, path: str):
        """
        Inicializa uma nova instância de MisaFile.

        Args:
            path (str): O caminho para o arquivo .misa.
        """
        self.path = path
        self.header = self._read_header()
```

### 1.3. Funções/Métodos

```python
def compress_rom(input_path: str, output_path: str, console: str):
    """
    Comprime uma ROM para o formato .misa.

    Args:
        input_path (str): Caminho para o arquivo da ROM de entrada.
        output_path (str): Caminho para o arquivo .misa de saída.
        console (str): O console de destino para otimização do coder.

    Returns:
        bool: True se a compressão foi bem-sucedida, False caso contrário.

    Raises:
        FileNotFoundError: Se o arquivo de entrada não for encontrado.
        ValueError: Se o console especificado não for suportado.
    """
    # Implementação da função
    pass
```

### 1.4. Estruturas de Dados (ex: `misa_meta`)

Para estruturas de dados complexas ou layouts de bytes, use docstrings para descrever os campos e seus propósitos.

```python
# Exemplo de como documentar a estrutura misa_meta (assumindo uma representação em Python)
class MisaMeta:
    """
    Estrutura de metadados para arquivos .misa.

    Esta estrutura de 70 bytes, comprimida com LZ4, contém informações essenciais
    para a identificação e gerenciamento da ROM.

    Campos:
        rom_id (bytes): ID único da ROM (16 bytes).
        console_id (int): ID numérico do console (2 bytes).
        crc32 (int): CRC32 da ROM original (4 bytes).
        compression_flags (int): Flags indicando coders usados (1 byte).
        original_size (int): Tamanho original da ROM em bytes (8 bytes).
        # ... outros campos
    """
    pass
```

## 2. Comentários de Código

Comentários devem ser usados para explicar o "porquê" de uma decisão de código, algoritmos complexos, ou seções não óbvias.

*   **Comentários de Linha Única**: Para explicações concisas.
    ```python
    # Verifica se o arquivo existe antes de prosseguir
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")
    ```
*   **Comentários de Bloco**: Para explicar seções maiores de lógica.
    ```python
    # Algoritmo de busca binária para encontrar o chunk correto
    # Isso otimiza o tempo de acesso para grandes arquivos .misa,
    # evitando a leitura sequencial de todos os chunks.
    low, high = 0, len(self.chunks) - 1
    while low <= high:
        mid = (low + high) // 2
        if self.chunks[mid].offset <= seek_pos < self.chunks[mid].offset + self.chunks[mid].size:
            return self.chunks[mid]
        elif seek_pos < self.chunks[mid].offset:
            high = mid - 1
        else:
            low = mid + 1
    ```

## 3. Ferramentas de Geração de Documentação

Recomendamos o uso do Sphinx com o plugin `sphinx.ext.autodoc` para gerar automaticamente a documentação a partir das docstrings.

### Exemplo de `conf.py` (Sphinx)

```python
# conf.py
import os
import sys
sys.path.insert(0, os.path.abspath('../src')) # Ajuste o caminho para o seu código

project = 'Mega_Emu_DataBase_ROMs'
copyright = '2025, Seu Nome'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon', # Para Google Style Docstrings
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
]
html_theme = 'sphinx_rtd_theme'
```

### Exemplo de `index.rst` (Sphinx)

```rst
.. Mega_Emu_DataBase_ROMs documentation master file, created by
   sphinx-quickstart on Tue Sep 10 16:00:00 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Mega_Emu_DataBase_ROMs's documentation!
===================================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
```

### Exemplo de `modules.rst` (Sphinx)

```rst
misa_modules
============

.. automodule:: compression
   :members:

.. automodule:: misa_format
   :members: