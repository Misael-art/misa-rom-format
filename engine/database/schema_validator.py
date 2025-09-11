#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validador de Schema de Banco de Dados

Este módulo fornece funcionalidades para validar e verificar a integridade
do schema do banco de dados em tempo de execução.

Autor: Sistema de Validação de Schema
Data: 2024
"""

import sqlite3
import logging
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Níveis de validação do schema."""
    BASIC = "basic"          # Verifica apenas existência de tabelas
    STANDARD = "standard"    # Verifica colunas obrigatórias
    STRICT = "strict"        # Verifica tipos, índices e constraints
    COMPLETE = "complete"    # Validação completa incluindo dados

@dataclass
class ValidationResult:
    """Resultado da validação do schema."""
    is_valid: bool
    level: ValidationLevel
    issues: List[str]
    warnings: List[str]
    missing_tables: List[str]
    missing_columns: List[str]
    missing_indexes: List[str]
    invalid_types: List[str]
    recommendations: List[str]
    
    def __post_init__(self):
        """Determina se o schema é válido baseado nos problemas encontrados."""
        critical_issues = (
            len(self.missing_tables) > 0 or 
            len(self.missing_columns) > 0 or
            len(self.issues) > 0
        )
        self.is_valid = not critical_issues

class SchemaValidator:
    """
    Validador de schema para banco de dados de ROMs.
    """
    
    def __init__(self):
        self.expected_schema = {
            'roms': {
                'columns': {
                    'id': {'type': 'INTEGER', 'nullable': False, 'primary_key': True},
                    'title': {'type': 'TEXT', 'nullable': True},
                    'description': {'type': 'TEXT', 'nullable': True},
                    'name_nointro': {'type': 'TEXT', 'nullable': True},
                    'name_goodtools': {'type': 'TEXT', 'nullable': True},
                    'name_TOSEC': {'type': 'TEXT', 'nullable': True},
                    'name_redump': {'type': 'TEXT', 'nullable': True},
                    'name_ROM_Header': {'type': 'TEXT', 'nullable': True},
                    'name_progetto_EMU': {'type': 'TEXT', 'nullable': True},
                    'name_custom': {'type': 'TEXT', 'nullable': True},
                    'name_unofficial_dumps': {'type': 'TEXT', 'nullable': True},
                    'flag': {'type': 'TEXT', 'nullable': True},
                    'language': {'type': 'TEXT', 'nullable': True},
                    'distribution': {'type': 'TEXT', 'nullable': True},
                    'versions': {'type': 'TEXT', 'nullable': True},
                    'region': {'type': 'TEXT', 'nullable': True},
                    'platform': {'type': 'TEXT', 'nullable': True},

                    'path_file': {'type': 'TEXT', 'nullable': True},
                    'path_image': {'type': 'TEXT', 'nullable': True},
                    'size_file': {'type': 'TEXT', 'nullable': True},
                    'crc': {'type': 'TEXT', 'nullable': True},
                    'md5': {'type': 'TEXT', 'nullable': True},
                    'sha1': {'type': 'TEXT', 'nullable': True, 'unique': True},
                    'sha256': {'type': 'TEXT', 'nullable': True},
                    'serial': {'type': 'TEXT', 'nullable': True},
                    'BIOS': {'type': 'BOOLEAN', 'nullable': True, 'default': 0},
                    'source_file': {'type': 'TEXT', 'nullable': True},
                    'date_added': {'type': 'TEXT', 'nullable': True, 'default': 'CURRENT_TIMESTAMP'}
                },
                'indexes': {
                    'idx_title': ['title'],
                    'idx_platform': ['platform'],
                    'idx_region': ['region'],
                    'idx_serial': ['serial'],
                    'idx_sha1': ['sha1']
                }
            },
            'database_info': {
                'columns': {
                    'key': {'type': 'TEXT', 'nullable': False, 'primary_key': True},
                    'value': {'type': 'TEXT', 'nullable': True}
                }
            }
        }
        
        self.critical_columns = {
            'roms': ['id', 'sha1', 'name', 'platform']
        }
    
    def validate_schema(self, db_path: str, level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        Valida o schema do banco de dados.
        
        Args:
            db_path: Caminho para o arquivo do banco de dados
            level: Nível de validação a ser aplicado
            
        Returns:
            Resultado da validação
        """
        result = ValidationResult(
            is_valid=True,
            level=level,
            issues=[],
            warnings=[],
            missing_tables=[],
            missing_columns=[],
            missing_indexes=[],
            invalid_types=[],
            recommendations=[]
        )
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Validação básica - existência de tabelas
            if level.value in ['basic', 'standard', 'strict', 'complete']:
                self._validate_tables(cursor, result)
            
            # Validação padrão - colunas obrigatórias
            if level.value in ['standard', 'strict', 'complete']:
                self._validate_columns(cursor, result)
            
            # Validação rigorosa - tipos e índices
            if level.value in ['strict', 'complete']:
                self._validate_types_and_indexes(cursor, result)
            
            # Validação completa - dados e performance
            if level.value == 'complete':
                self._validate_data_integrity(cursor, result)
            
            conn.close()
            
        except Exception as e:
            result.issues.append(f"Erro durante validação: {str(e)}")
            logger.error(f"Erro na validação do schema: {e}")
        
        return result
    
    def _validate_tables(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """
        Valida a existência das tabelas necessárias.
        """
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            for table_name in self.expected_schema.keys():
                if table_name not in existing_tables:
                    result.missing_tables.append(table_name)
                    result.issues.append(f"Tabela '{table_name}' não encontrada")
            
            logger.debug(f"Tabelas encontradas: {existing_tables}")
            
        except Exception as e:
            result.issues.append(f"Erro ao verificar tabelas: {str(e)}")
    
    def _validate_columns(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """
        Valida a existência das colunas necessárias.
        """
        for table_name, table_schema in self.expected_schema.items():
            if table_name in result.missing_tables:
                continue  # Pula se a tabela não existe
            
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = {row[1]: row for row in cursor.fetchall()}
                
                for col_name, col_spec in table_schema['columns'].items():
                    if col_name not in existing_columns:
                        result.missing_columns.append(f"{table_name}.{col_name}")
                        
                        # Verifica se é uma coluna crítica
                        if (table_name in self.critical_columns and 
                            col_name in self.critical_columns[table_name]):
                            result.issues.append(
                                f"Coluna crítica '{col_name}' faltando na tabela '{table_name}'"
                            )
                        else:
                            result.warnings.append(
                                f"Coluna '{col_name}' faltando na tabela '{table_name}'"
                            )
                
                logger.debug(f"Colunas da tabela {table_name}: {list(existing_columns.keys())}")
                
            except Exception as e:
                result.issues.append(f"Erro ao verificar colunas da tabela '{table_name}': {str(e)}")
    
    def _validate_types_and_indexes(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """
        Valida tipos de dados e índices.
        """
        for table_name, table_schema in self.expected_schema.items():
            if table_name in result.missing_tables:
                continue
            
            # Valida índices
            if 'indexes' in table_schema:
                try:
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
                        (table_name,)
                    )
                    existing_indexes = {row[0] for row in cursor.fetchall()}
                    
                    for index_name in table_schema['indexes'].keys():
                        if index_name not in existing_indexes:
                            result.missing_indexes.append(f"{table_name}.{index_name}")
                            result.warnings.append(
                                f"Índice '{index_name}' faltando na tabela '{table_name}'"
                            )
                    
                except Exception as e:
                    result.warnings.append(
                        f"Erro ao verificar índices da tabela '{table_name}': {str(e)}"
                    )
    
    def _validate_data_integrity(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """
        Valida a integridade dos dados.
        """
        try:
            # Verifica duplicatas em colunas únicas
            cursor.execute("""
                SELECT sha1, COUNT(*) as count 
                FROM roms 
                WHERE sha1 IS NOT NULL AND sha1 != '' 
                GROUP BY sha1 
                HAVING count > 1
            """)
            
            duplicates = cursor.fetchall()
            if duplicates:
                result.warnings.append(
                    f"Encontradas {len(duplicates)} duplicatas na coluna sha1"
                )
            
            # Verifica registros com dados críticos faltando
            cursor.execute("""
                SELECT COUNT(*) FROM roms 
                WHERE (title IS NULL OR title = '') 
                   OR (platform IS NULL OR platform = '')
            """)
            
            incomplete_records = cursor.fetchone()[0]
            if incomplete_records > 0:
                result.warnings.append(
                    f"{incomplete_records} registros com dados críticos faltando"
                )
            
            # Recomendações de performance
            cursor.execute("SELECT COUNT(*) FROM roms")
            total_records = cursor.fetchone()[0]
            
            if total_records > 10000:
                result.recommendations.append(
                    "Considere implementar particionamento para melhor performance"
                )
            
            if len(result.missing_indexes) > 0:
                result.recommendations.append(
                    "Criar índices faltantes para melhorar performance de consultas"
                )
            
        except Exception as e:
            result.warnings.append(f"Erro durante validação de integridade de dados: {str(e)}")
    
    def get_repair_suggestions(self, validation_result: ValidationResult) -> List[str]:
        """
        Gera sugestões de reparo baseadas no resultado da validação.
        
        Args:
            validation_result: Resultado da validação
            
        Returns:
            Lista de sugestões de reparo
        """
        suggestions = []
        
        if validation_result.missing_tables:
            suggestions.append(
                "Execute o script de migração para criar tabelas faltantes"
            )
        
        if validation_result.missing_columns:
            suggestions.append(
                "Use ALTER TABLE para adicionar colunas faltantes"
            )
        
        if validation_result.missing_indexes:
            suggestions.append(
                "Execute CREATE INDEX para criar índices faltantes"
            )
        
        if not validation_result.is_valid:
            suggestions.append(
                "Considere usar o script de migração automática para corrigir problemas"
            )
        
        return suggestions
    
    def auto_fix_schema(self, db_path: str, backup: bool = True) -> bool:
        """
        Tenta corrigir automaticamente problemas de schema.
        
        Args:
            db_path: Caminho para o banco de dados
            backup: Se deve criar backup antes das correções
            
        Returns:
            True se as correções foram aplicadas com sucesso
        """
        try:
            from .migration_script import DatabaseMigrator
            
            migrator = DatabaseMigrator()
            return migrator.migrate_database(db_path, backup)
            
        except ImportError:
            logger.error("Módulo de migração não encontrado")
            return False
        except Exception as e:
            logger.error(f"Erro durante correção automática: {e}")
            return False

def validate_database_schema(db_path: str, level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """
    Função de conveniência para validar schema de banco de dados.
    
    Args:
        db_path: Caminho para o arquivo do banco de dados
        level: Nível de validação
        
    Returns:
        Resultado da validação
    """
    validator = SchemaValidator()
    return validator.validate_schema(db_path, level)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python schema_validator.py <caminho_do_banco>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    level = ValidationLevel.STANDARD
    
    if len(sys.argv) > 2:
        level_str = sys.argv[2].lower()
        level = ValidationLevel(level_str) if level_str in [l.value for l in ValidationLevel] else ValidationLevel.STANDARD
    
    result = validate_database_schema(db_path, level)
    
    print(f"Validação do Schema - Nível: {level.value}")
    print(f"Válido: {'✓' if result.is_valid else '✗'}")
    
    if result.issues:
        print("\nProblemas Críticos:")
        for issue in result.issues:
            print(f"  ✗ {issue}")
    
    if result.warnings:
        print("\nAvisos:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")
    
    if result.recommendations:
        print("\nRecomendações:")
        for rec in result.recommendations:
            print(f"  💡 {rec}")