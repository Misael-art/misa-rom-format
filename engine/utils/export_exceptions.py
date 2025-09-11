#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Export Exceptions
Define exceções personalizadas para exportação de dados
"""

class ExportError(Exception):
    """Classe base para erros de exportação."""
    pass

class InvalidDataError(ExportError):
    """Erro para dados inválidos."""
    pass

class FileError(ExportError):
    """Erro para problemas com arquivos."""
    pass

class FormatError(ExportError):
    """Erro para formatos inválidos ou não suportados."""
    pass

class ValidationError(ExportError):
    """Erro para falhas de validação."""
    pass

class ConversionError(ExportError):
    """Erro para falhas na conversão de dados."""
    pass

class PermissionError(ExportError):
    """Erro para problemas de permissão."""
    pass

class MemoryError(ExportError):
    """Erro para problemas de memória."""
    pass

class TimeoutError(ExportError):
    """Erro para operações que excederam o tempo limite."""
    pass

class CancellationError(ExportError):
    """Erro para operações canceladas pelo usuário."""
    pass 