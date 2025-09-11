#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Export Utils
Utilitários para exportação de dados em vários formatos
"""

import os
import json
import csv
import yaml
import xml.dom.minidom
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
import tempfile
import shutil
import logging
import re
import html

from .export_formats import (
    SUPPORTED_FORMATS,
    DEFAULT_HTML_STYLES,
    DEFAULT_MD_TEMPLATE,
    get_format_config,
    is_format_supported,
    get_extension,
    get_mime_type
)

from .export_exceptions import (
    ExportError,
    InvalidDataError,
    FileError,
    FormatError,
    ValidationError,
    ConversionError,
    PermissionError,
    MemoryError,
    TimeoutError,
    CancellationError
)

# Logger
logger = logging.getLogger(__name__)

class ExportUtils:
    """
    Classe de utilidades para exportação de dados em vários formatos.
    Suporta exportação para JSON, XML, CSV, HTML, YAML e Markdown.
    """
    
    @staticmethod
    def validate_data(data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> None:
        """
        Valida os dados para exportação.
        
        Args:
            data: Dados a serem validados
            
        Raises:
            InvalidDataError: Se os dados forem inválidos
        """
        if not data:
            raise InvalidDataError("Dados vazios")
            
        if isinstance(data, dict):
            return
            
        if not isinstance(data, list):
            raise InvalidDataError("Dados devem ser lista ou dicionário")
            
        if not all(isinstance(item, dict) for item in data):
            raise InvalidDataError("Todos os itens devem ser dicionários")
    
    @staticmethod
    def validate_file_path(file_path: Union[str, Path], format_name: str) -> Path:
        """
        Valida e normaliza o caminho do arquivo.
        
        Args:
            file_path: Caminho do arquivo
            format_name: Nome do formato
            
        Returns:
            Path normalizado
            
        Raises:
            FileError: Se o caminho for inválido
            FormatError: Se o formato for inválido
        """
        try:
            if not is_format_supported(format_name):
                raise FormatError(f"Formato não suportado: {format_name}")
            
            path = Path(file_path)
            
            # Verifica extensão
            expected_ext = get_extension(format_name)
            if path.suffix.lower() != expected_ext:
                path = path.with_suffix(expected_ext)
            
            # Cria diretório pai
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Verifica permissões
            if path.exists() and not os.access(path.parent, os.W_OK):
                raise PermissionError(f"Sem permissão de escrita: {path}")
            
            return path
            
        except (FileError, FormatError, PermissionError):
            raise
        except Exception as e:
            raise FileError(f"Erro ao validar caminho: {e}")
    
    @staticmethod
    def create_temp_file(format_name: str) -> tuple[Path, Any]:
        """
        Cria um arquivo temporário para exportação.
        
        Args:
            format_name: Nome do formato
            
        Returns:
            Tupla com caminho do arquivo e objeto de arquivo
            
        Raises:
            FileError: Se houver erro ao criar arquivo
        """
        try:
            # Obtém extensão do formato
            ext = get_extension(format_name)
            
            # Cria arquivo temporário
            fd, temp_path = tempfile.mkstemp(suffix=ext)
            temp_file = os.fdopen(fd, 'w', encoding='utf-8')
            
            return Path(temp_path), temp_file
            
        except Exception as e:
            raise FileError(f"Erro ao criar arquivo temporário: {e}")
    
    @staticmethod
    def move_temp_file(temp_path: Path, final_path: Path) -> None:
        """
        Move o arquivo temporário para o destino final.
        
        Args:
            temp_path: Caminho do arquivo temporário
            final_path: Caminho final
            
        Raises:
            FileError: Se houver erro ao mover arquivo
        """
        try:
            shutil.move(str(temp_path), str(final_path))
        except Exception as e:
            raise FileError(f"Erro ao mover arquivo: {e}")
            
    @staticmethod
    def cleanup_temp_file(temp_path: Path) -> None:
        """
        Remove um arquivo temporário.
        
        Args:
            temp_path: Caminho do arquivo temporário
        """
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception as e:
            logger.warning(f"Erro ao remover arquivo temporário: {e}")
    
    @staticmethod
    def get_supported_formats() -> Dict[str, Dict[str, str]]:
        """
        Retorna os formatos suportados.
        
        Returns:
            Dicionário com informações dos formatos
        """
        return SUPPORTED_FORMATS
    
    @staticmethod
    def export_to_csv(
        data: List[Dict[str, Any]],
        file_path: Union[str, Path],
        columns: Optional[List[str]] = None,
        headers: Optional[List[str]] = None,
        dialect: str = 'excel',
        delimiter: str = ',',
        quotechar: str = '"',
        encoding: str = 'utf-8',
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Exporta dados para um arquivo CSV.
        
        Args:
            data: Lista de dicionários com os dados a exportar
            file_path: Caminho do arquivo CSV a ser criado
            columns: Lista de chaves a serem incluídas (opcional)
            headers: Lista de cabeçalhos personalizados (opcional)
            dialect: Dialeto CSV ('excel', 'excel-tab', 'unix')
            delimiter: Caractere delimitador
            quotechar: Caractere para aspas
            encoding: Codificação do arquivo
            progress_callback: Função para relatar progresso
                Parâmetros: (float percentual, int processados, int total)
                Retorno: True para continuar, False para cancelar
                
        Returns:
            True se a exportação foi bem-sucedida
            
        Raises:
            InvalidDataError: Se os dados forem inválidos
            FileError: Se houver erro ao criar/escrever arquivo
            FormatError: Se o formato CSV for inválido
        """
        try:
            # Valida dados
            ExportUtils.validate_data(data)
            if not isinstance(data, list):
                raise InvalidDataError("Dados devem ser uma lista para CSV")
            
            # Valida e normaliza caminho
            path = ExportUtils.validate_file_path(file_path, 'csv')
            
            # Se colunas não foram especificadas, usa todas as chaves do primeiro item
            if not columns and data:
                columns = list(data[0].keys())
            
            # Se cabeçalhos não foram especificados, usa nomes das colunas
            if not headers:
                headers = columns
            
            # Valida colunas e cabeçalhos
            if not columns or not headers:
                raise InvalidDataError("Colunas/cabeçalhos não podem ser vazios")
            if len(columns) != len(headers):
                raise InvalidDataError("Número de colunas e cabeçalhos deve ser igual")
            
            # Cria arquivo temporário
            temp_path, temp_file = ExportUtils.create_temp_file('csv')
            
            try:
                # Configura writer CSV
                writer = csv.writer(
                    temp_file,
                    dialect=dialect,
                    delimiter=delimiter,
                    quotechar=quotechar,
                    quoting=csv.QUOTE_MINIMAL
                )
                
                # Escreve o cabeçalho
                writer.writerow(headers)
                
                # Escreve os dados
                total = len(data)
                for i, item in enumerate(data):
                    try:
                        # Cria a linha com os valores das colunas especificadas
                        row = []
                        for col in columns:
                            value = item.get(col)
                            
                            # Formata o valor
                            if isinstance(value, (list, dict, set)):
                                value = json.dumps(value, ensure_ascii=False)
                            elif isinstance(value, datetime):
                                value = value.isoformat()
                            elif value is None:
                                value = ''
                            else:
                                value = str(value)
                            
                            row.append(value)
                        
                        # Escreve a linha
                        writer.writerow(row)
                        
                        # Atualiza o progresso
                        if progress_callback and i % 100 == 0:  # A cada 100 itens
                            progress = (i + 1) / total * 100
                            if not progress_callback(progress, i + 1, total):
                                logger.info("Exportação para CSV cancelada pelo usuário")
                                return False
                            
                    except Exception as e:
                        logger.error(f"Erro ao processar item {i}: {e}")
                        continue
                
                # Fecha arquivo temporário
                temp_file.close()
                
                # Move para destino final
                ExportUtils.move_temp_file(temp_path, path)
                
                # Finaliza o progresso
                if progress_callback:
                    progress_callback(100, total, total)
                    
                logger.info(f"Dados exportados com sucesso para CSV: {path}")
                return True
                
            finally:
                # Fecha e remove arquivo temporário em caso de erro
                temp_file.close()
                ExportUtils.cleanup_temp_file(temp_path)
            
        except (InvalidDataError, FileError, FormatError):
            raise
        except Exception as e:
            raise ExportError(f"Erro ao exportar para CSV: {e}")
    
    @staticmethod
    def export_to_json(
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        file_path: Union[str, Path],
        indent: Optional[int] = None,
        ensure_ascii: Optional[bool] = None,
        sort_keys: Optional[bool] = None,
        encoding: str = 'utf-8',
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Exporta dados para JSON.
        
        Args:
            data: Dados a exportar
            file_path: Caminho do arquivo
            indent: Indentação (None para minificado)
            ensure_ascii: Usar apenas caracteres ASCII
            sort_keys: Ordenar chaves
            encoding: Codificação do arquivo
            progress_callback: Função de callback de progresso
            
        Returns:
            bool: True se exportado com sucesso
            
        Raises:
            ExportError: Se houver erro na exportação
        """
        try:
            # Valida dados
            ExportUtils.validate_data(data)
            
            # Valida e normaliza caminho
            path = ExportUtils.validate_file_path(file_path, 'json')
            
            # Obtém configurações do formato
            config = get_format_config('json')
            default_config = config['default_config']
            
            # Usa valores padrão se não especificados
            if indent is None:
                indent = default_config['indent']
            if ensure_ascii is None:
                ensure_ascii = default_config['ensure_ascii']
            if sort_keys is None:
                sort_keys = default_config['sort_keys']
            
            # Cria arquivo temporário
            temp_path, temp_file = ExportUtils.create_temp_file('json')
            
            try:
                # Classe para codificar tipos especiais
                class JSONEncoder(json.JSONEncoder):
                    def default(self, obj):
                        if isinstance(obj, datetime):
                            return obj.isoformat()
                        elif isinstance(obj, (set, frozenset)):
                            return list(obj)
                        elif isinstance(obj, bytes):
                            return obj.decode(encoding)
                        elif isinstance(obj, Path):
                            return str(obj)
                        return super().default(obj)
                
                # Calcula o total de itens para progresso
                total = len(data) if isinstance(data, list) else 1
                
                # Serializa os dados
                json.dump(
                    data,
                    temp_file,
                    indent=indent,
                    ensure_ascii=ensure_ascii,
                    sort_keys=sort_keys,
                    cls=JSONEncoder
                )
                
                # Fecha o arquivo
                temp_file.close()
                
                # Move para o destino final
                ExportUtils.move_temp_file(temp_path, path)
                
                return True
                
            except Exception as e:
                raise ConversionError(f"Erro ao converter para JSON: {e}")
            finally:
                # Limpa arquivo temporário
                ExportUtils.cleanup_temp_file(temp_path)
                
        except ExportError:
            raise
        except Exception as e:
            raise ExportError(f"Erro na exportação JSON: {e}")
    
    @staticmethod
    def export_to_xml(
        data: List[Dict[str, Any]],
        file_path: Union[str, Path],
        root_element: Optional[str] = None,
        row_element: Optional[str] = None,
        indent: Optional[str] = None,
        encoding: str = 'utf-8',
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Exporta dados para XML.
        
        Args:
            data: Dados a exportar
            file_path: Caminho do arquivo
            root_element: Nome do elemento raiz
            row_element: Nome do elemento de linha
            indent: String de indentação
            encoding: Codificação do arquivo
            progress_callback: Função de callback de progresso
            
        Returns:
            bool: True se exportado com sucesso
            
        Raises:
            ExportError: Se houver erro na exportação
        """
        try:
            # Valida dados
            ExportUtils.validate_data(data)
            if not isinstance(data, list):
                raise InvalidDataError("Dados devem ser uma lista para XML")
            
            # Valida e normaliza caminho
            path = ExportUtils.validate_file_path(file_path, 'xml')
            
            # Obtém configurações do formato
            config = get_format_config('xml')
            default_config = config['default_config']
            
            # Usa valores padrão se não especificados
            if root_element is None:
                root_element = default_config['root_element']
            if row_element is None:
                row_element = default_config['row_element']
            if indent is None:
                indent = default_config['indent']
            
            # Cria arquivo temporário
            temp_path, temp_file = ExportUtils.create_temp_file('xml')
            
            try:
                # Cria documento XML
                doc = xml.dom.minidom.Document()
                
                # Cria elemento raiz
                root = doc.createElement(root_element)
                doc.appendChild(root)
                
                # Função para converter valor para string XML
                def value_to_xml_str(value: Any) -> str:
                    if isinstance(value, (list, dict, set)):
                        return json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, datetime):
                        return value.isoformat()
                    elif isinstance(value, bool):
                        return str(value).lower()
                    elif value is None:
                        return ''
                    return str(value)
                
                # Função para criar elemento XML
                def create_element(name: str, value: Any) -> xml.dom.minidom.Element:
                    elem = doc.createElement(name)
                    # Remove caracteres inválidos do nome
                    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
                    # Converte valor para texto
                    text = value_to_xml_str(value)
                    if text:
                        text_node = doc.createTextNode(text)
                        elem.appendChild(text_node)
                    return elem
                
                # Processa cada item
                total = len(data)
                for i, item in enumerate(data, 1):
                    # Verifica cancelamento
                    if progress_callback:
                        progress = (i / total) * 100
                        if not progress_callback(progress, i, total):
                            raise CancellationError("Exportação cancelada pelo usuário")
                    
                    # Cria elemento para o item
                    item_elem = doc.createElement(row_element)
                    
                    # Adiciona campos do item
                    for key, value in item.items():
                        field_elem = create_element(key, value)
                        item_elem.appendChild(field_elem)
                    
                    # Adiciona ao documento
                    root.appendChild(item_elem)
                
                # Escreve o documento
                xml_str = doc.toprettyxml(indent=indent, encoding=encoding)
                temp_file.buffer.write(xml_str)
                
                # Fecha o arquivo
                temp_file.close()
                
                # Move para o destino final
                ExportUtils.move_temp_file(temp_path, path)
                
                return True
                
            except Exception as e:
                raise ConversionError(f"Erro ao converter para XML: {e}")
            finally:
                # Limpa arquivo temporário
                ExportUtils.cleanup_temp_file(temp_path)
                
        except ExportError:
            raise
        except Exception as e:
            raise ExportError(f"Erro na exportação XML: {e}")
    
    @staticmethod
    def export_to_html(
        data: List[Dict[str, Any]],
        file_path: Union[str, Path],
        title: str = 'Exported Data',
        columns: Optional[List[str]] = None,
        headers: Optional[List[str]] = None,
        css: Optional[str] = None,
        encoding: str = 'utf-8',
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Exporta dados para um arquivo HTML.
        
        Args:
            data: Lista de dicionários com os dados
            file_path: Caminho do arquivo HTML a ser criado
            title: Título da página HTML
            columns: Lista de chaves a serem incluídas (opcional)
            headers: Lista de cabeçalhos personalizados (opcional)
            css: CSS personalizado (opcional)
            encoding: Codificação do arquivo
            progress_callback: Função para relatar progresso
                Parâmetros: (float percentual, int processados, int total)
                Retorno: True para continuar, False para cancelar
                
        Returns:
            True se a exportação foi bem-sucedida
            
        Raises:
            InvalidDataError: Se os dados forem inválidos
            FileError: Se houver erro ao criar/escrever arquivo
            FormatError: Se o formato HTML for inválido
        """
        try:
            # Valida dados
            ExportUtils.validate_data(data)
            if not isinstance(data, list):
                raise InvalidDataError("Dados devem ser uma lista para HTML")
            
            # Valida e normaliza caminho
            path = ExportUtils.validate_file_path(file_path, 'html')
            
            # Se colunas não foram especificadas, usa todas as chaves do primeiro item
            if not columns and data:
                columns = list(data[0].keys())
            
            # Se cabeçalhos não foram especificados, usa nomes das colunas
            if not headers:
                headers = columns
            
            # Valida colunas e cabeçalhos
            if not columns or not headers:
                raise InvalidDataError("Colunas/cabeçalhos não podem ser vazios")
            if len(columns) != len(headers):
                raise InvalidDataError("Número de colunas e cabeçalhos deve ser igual")
            
            # CSS padrão se não fornecido
            if css is None:
                css = """
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }
                h1 {
                    color: #333;
                    text-align: center;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    background-color: white;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                }
                th, td {
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                th {
                    background-color: #4CAF50;
                    color: white;
                }
                tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                tr:hover {
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .footer {
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                    font-size: 0.8em;
                }
                """
            
            # Cria arquivo temporário
            temp_path, temp_file = ExportUtils.create_temp_file('html')
            
            try:
                # Função para converter valor para string HTML
                def value_to_html_str(value: Any) -> str:
                    if isinstance(value, (list, dict, set)):
                        return html.escape(json.dumps(value, ensure_ascii=False))
                    elif isinstance(value, datetime):
                        return html.escape(value.isoformat())
                    elif isinstance(value, bool):
                        return html.escape(str(value).lower())
                    elif value is None:
                        return ''
                    return html.escape(str(value))
                
                # Escreve o cabeçalho HTML
                temp_file.write(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="{encoding}">
        except (FileNotFoundError, PermissionError, OSError) as e:
        logger.error(f"Erro em export_to_html: {e}", exc_info=True)
        raise
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        {css}
    </style>
</head>
<body>
    <div class="container">
        <h1>{html.escape(title)}</h1>
        <table>
            <thead>
                <tr>
""")
                
                # Escreve os cabeçalhos da tabela
                for header in headers:
                    temp_file.write(f'                    <th>{html.escape(header)}</th>\n')
                
                temp_file.write("""                </tr>
            </thead>
            <tbody>
""")
                
                # Processa cada item
                total = len(data)
                for i, item in enumerate(data):
                    try:
                        # Abre a linha
                        temp_file.write('                <tr>\n')
                        
                        # Escreve cada coluna
                        for col in columns:
                            value = item.get(col)
                            value_str = value_to_html_str(value)
                            temp_file.write(f'                    <td>{value_str}</td>\n')
                        
                        # Fecha a linha
                        temp_file.write('                </tr>\n')
                        
                        # Atualiza progresso
                        if progress_callback and i % 100 == 0:
                            progress = (i + 1) / total * 100
                            if not progress_callback(progress, i + 1, total):
                                logger.info("Exportação para HTML cancelada pelo usuário")
                                return False
                            
                    except Exception as e:
                        logger.error(f"Erro ao processar item {i}: {e}")
                        continue
                
                # Escreve o rodapé HTML
                temp_file.write(f"""            </tbody>
        </table>
        <div class="footer">
            Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        </div>
    </div>
</body>
</html>
""")
                
                # Fecha arquivo temporário
                temp_file.close()
                
                # Move para destino final
                ExportUtils.move_temp_file(temp_path, path)
                
                # Finaliza o progresso
                if progress_callback:
                    progress_callback(100, total, total)
                
                logger.info(f"Dados exportados com sucesso para HTML: {path}")
                return True
                
            finally:
                # Fecha e remove arquivo temporário em caso de erro
                temp_file.close()
                ExportUtils.cleanup_temp_file(temp_path)
            
        except (InvalidDataError, FileError, FormatError):
            raise
        except Exception as e:
            raise ExportError(f"Erro ao exportar para HTML: {e}")
    
    @staticmethod
    def export_to_markdown(
        data: List[Dict[str, Any]],
        file_path: Union[str, Path],
        title: Optional[str] = None,
        include_metadata: Optional[bool] = None,
        encoding: str = 'utf-8',
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Exporta dados para Markdown.
        
        Args:
            data: Dados a exportar
            file_path: Caminho do arquivo
            title: Título do documento
            include_metadata: Incluir metadados YAML
            encoding: Codificação do arquivo
            progress_callback: Função de callback de progresso
            
        Returns:
            bool: True se exportado com sucesso
            
        Raises:
            ExportError: Se houver erro na exportação
        """
        try:
            # Valida dados
            ExportUtils.validate_data(data)
            if not isinstance(data, list):
                raise InvalidDataError("Dados devem ser uma lista para Markdown")
            if not data:
                raise InvalidDataError("Lista de dados vazia")
            
            # Valida e normaliza caminho
            path = ExportUtils.validate_file_path(file_path, 'md')
            
            # Obtém configurações do formato
            config = get_format_config('markdown')
            default_config = config['default_config']
            
            # Usa valores padrão se não especificados
            if title is None:
                title = default_config['title']
            if include_metadata is None:
                include_metadata = default_config['include_metadata']
            
            # Cria arquivo temporário
            temp_path, temp_file = ExportUtils.create_temp_file('md')
            
            try:
                # Função para escapar caracteres especiais Markdown
                def escape_markdown(text: str) -> str:
                    special_chars = r'[\_*#{}`|]'
                    return re.sub(special_chars, r'\\\g<0>', str(text))
                
                # Função para converter valor para Markdown
                def value_to_markdown(value: Any) -> str:
                    if isinstance(value, (dict, list, set)):
                        return f'`{escape_markdown(json.dumps(value, ensure_ascii=False))}`'
                    elif isinstance(value, datetime):
                        return escape_markdown(value.isoformat())
                    elif isinstance(value, bool):
                        return escape_markdown(str(value).lower())
                    elif value is None:
                        return ''
                    return escape_markdown(str(value))
                
                # Obtém cabeçalhos das colunas
                headers = list(data[0].keys())
                
                # Gera conteúdo Markdown
                md_content = []
                
                # Adiciona metadados YAML se solicitado
                if include_metadata:
                    metadata = {
                        'title': title,
                        'date': datetime.now().isoformat(),
                        'format': 'markdown',
                        'columns': len(headers),
                        'rows': len(data)
                    }
                    md_content.extend([
                        '---',
                        yaml.dump(metadata, allow_unicode=True, default_flow_style=False),
                        '---',
                        ''
                    ])
                
                # Adiciona título
                md_content.extend([
                    f'# {escape_markdown(title)}',
                    ''
                ])
                
                # Adiciona cabeçalhos da tabela
                md_content.append('| ' + ' | '.join(escape_markdown(h) for h in headers) + ' |')
                
                # Adiciona linha de separação
                md_content.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                
                # Processa cada item
                total = len(data)
                for i, item in enumerate(data, 1):
                    # Verifica cancelamento
                    if progress_callback:
                        progress = (i / total) * 100
                        if not progress_callback(progress, i, total):
                            raise CancellationError("Exportação cancelada pelo usuário")
                    
                    # Adiciona linha
                    row = []
                    for header in headers:
                        value = item.get(header, '')
                        row.append(value_to_markdown(value))
                    md_content.append('| ' + ' | '.join(row) + ' |')
                
                # Adiciona nota de rodapé
                md_content.extend([
                    '',
                    f'*Gerado em {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*'
                ])
                
                # Escreve arquivo
                temp_file.write('\n'.join(md_content))
                
                # Fecha o arquivo
                temp_file.close()
                
                # Move para o destino final
                ExportUtils.move_temp_file(temp_path, path)
                
                return True
                
            except Exception as e:
                raise ConversionError(f"Erro ao converter para Markdown: {e}")
            finally:
                # Limpa arquivo temporário
                ExportUtils.cleanup_temp_file(temp_path)
                
        except ExportError:
            raise
        except Exception as e:
            raise ExportError(f"Erro na exportação Markdown: {e}")
    
    @staticmethod
    def export_to_yaml(
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        file_path: Union[str, Path],
        flow_style: Optional[bool] = None,
        indent: Optional[int] = None,
        encoding: str = 'utf-8',
        progress_callback: Optional[Callable[[float, int, int], bool]] = None
    ) -> bool:
        """
        Exporta dados para YAML.
        
        Args:
            data: Dados a exportar
            file_path: Caminho do arquivo
            flow_style: Usar estilo de fluxo
            indent: Indentação
            encoding: Codificação do arquivo
            progress_callback: Função de callback de progresso
            
        Returns:
            bool: True se exportado com sucesso
            
        Raises:
            ExportError: Se houver erro na exportação
        """
        try:
            # Valida dados
            ExportUtils.validate_data(data)
            
            # Valida e normaliza caminho
            path = ExportUtils.validate_file_path(file_path, 'yaml')
            
            # Obtém configurações do formato
            config = get_format_config('yaml')
            default_config = config['default_config']
            
            # Usa valores padrão se não especificados
            if flow_style is None:
                flow_style = default_config['flow_style']
            if indent is None:
                indent = default_config['indent']
            
            # Cria arquivo temporário
            temp_path, temp_file = ExportUtils.create_temp_file('yaml')
            
            try:
                # Classe para representar tipos especiais em YAML
                class YAMLDumper(yaml.SafeDumper):
                    def represent_datetime(self, data):
                        return self.represent_scalar('tag:yaml.org,2002:timestamp', data.isoformat())
                    
                    def represent_set(self, data):
                        return self.represent_sequence('tag:yaml.org,2002:seq', list(data))
                    
                    def represent_bytes(self, data):
                        return self.represent_scalar('tag:yaml.org,2002:str', data.decode(encoding))
                    
                    def represent_path(self, data):
                        return self.represent_scalar('tag:yaml.org,2002:str', str(data))
                
                # Registra representadores
                YAMLDumper.add_representer(datetime, YAMLDumper.represent_datetime)
                YAMLDumper.add_representer(set, YAMLDumper.represent_set)
                YAMLDumper.add_representer(frozenset, YAMLDumper.represent_set)
                YAMLDumper.add_representer(bytes, YAMLDumper.represent_bytes)
                YAMLDumper.add_representer(Path, YAMLDumper.represent_path)
                
                # Calcula o total de itens para progresso
                total = len(data) if isinstance(data, list) else 1
                
                # Serializa os dados
                yaml.dump(
                    data,
                    temp_file,
                    Dumper=YAMLDumper,
                    default_flow_style=flow_style,
                    indent=indent,
                    allow_unicode=True,
                    encoding=encoding
                )
                
                # Fecha o arquivo
                temp_file.close()
                
                # Move para o destino final
                ExportUtils.move_temp_file(temp_path, path)
                
                return True
                
            except Exception as e:
                raise ConversionError(f"Erro ao converter para YAML: {e}")
            finally:
                # Limpa arquivo temporário
                ExportUtils.cleanup_temp_file(temp_path)
                
        except ExportError:
            raise
        except Exception as e:
            raise ExportError(f"Erro na exportação YAML: {e}") 