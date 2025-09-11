#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Gerenciador de Configurações
Responsável por gerenciar as configurações do aplicativo
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Union

# Logger
logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Gerencia as configurações do aplicativo.
    
    Fornece métodos para carregar, salvar e acessar configurações
    armazenadas em um arquivo JSON.
    """
    
    def __init__(self, config_file: str = "config.json"):
        """
        Inicializa o gerenciador de configurações.
        
        Args:
            config_file: Caminho para o arquivo de configuração
        """
        self.config_file = config_file
        self.config = {
            "theme": "light",  # light ou dark
            "last_db_path": "",
            "window_size": "1024x768",
            "language": "pt_BR",
            "show_navigation": True,
            "enable_expansions": True,  # Suporte a expansões
            "enable_accessories": True,  # Suporte a acessórios
            "advanced_timing": False,    # Sistema de timing avançado
            "recent_databases": []
        }
        
        # Tenta carregar as configurações existentes
        self.load()
    
    def load(self) -> bool:
        """
        Carrega as configurações do arquivo.
        
        Returns:
            True se as configurações foram carregadas com sucesso, False caso contrário
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    
                    # Atualiza as configurações carregadas, mantendo valores padrão
                    # para chaves que não estão no arquivo
                    self.config.update(loaded_config)
                    
                logger.info(f"Configurações carregadas de {self.config_file}")
                return True
            else:
                logger.info(f"Arquivo de configuração {self.config_file} não encontrado. Usando valores padrão.")
                return False
        except Exception as e:
            logger.exception(f"Erro ao carregar configurações de {self.config_file}")
            return False
    
    def save(self) -> bool:
        """
        Salva as configurações no arquivo.
        
        Returns:
            True se as configurações foram salvas com sucesso, False caso contrário
        """
        try:
            # Garante que o diretório existe
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # Salva o arquivo
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
                
            logger.info(f"Configurações salvas em {self.config_file}")
            return True
        except Exception as e:
            logger.exception(f"Erro ao salvar configurações em {self.config_file}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém um valor da configuração.
        
        Args:
            key: Chave da configuração
            default: Valor padrão caso a chave não exista
            
        Returns:
            Valor da configuração ou o valor padrão
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """
        Define um valor na configuração e salva o arquivo.
        
        Args:
            key: Chave da configuração
            value: Valor a ser definido
            
        Returns:
            True se o valor foi definido e salvo com sucesso, False caso contrário
        """
        try:
            self.config[key] = value
            return self.save()
        except Exception as e:
            logger.exception(f"Erro ao definir configuração '{key}'")
            return False
    
    def add_to_recent_databases(self, db_path: str, max_items: int = 10) -> bool:
        """
        Adiciona um caminho de banco de dados à lista de recentes.
        
        O item adicionado vai para o topo da lista. Se já existir na lista,
        ele é movido para o topo. Se a lista exceder o número máximo de itens,
        o item mais antigo é removido.
        
        Args:
            db_path: Caminho do banco de dados
            max_items: Número máximo de itens na lista
            
        Returns:
            True se a operação foi bem-sucedida, False caso contrário
        """
        try:
            # Normaliza o caminho
            db_path = os.path.normpath(db_path)
            
            # Obtém a lista atual
            recent = self.get("recent_databases", [])
            
            # Remove o caminho se já existir
            if db_path in recent:
                recent.remove(db_path)
            
            # Adiciona ao início da lista
            recent.insert(0, db_path)
            
            # Limita o tamanho da lista
            if len(recent) > max_items:
                recent = recent[:max_items]
            
            # Atualiza a configuração
            self.set("recent_databases", recent)
            
            # Define também como último banco de dados usado
            self.set("last_db_path", db_path)
            
            return True
        except Exception as e:
            logger.exception("Erro ao adicionar banco de dados recente")
            return False
    
    def clear_recent_databases(self) -> bool:
        """
        Limpa a lista de bancos de dados recentes.
        
        Returns:
            True se a operação foi bem-sucedida, False caso contrário
        """
        return self.set("recent_databases", [])
    
    def get_theme_colors(self) -> Dict[str, str]:
        """
        Retorna as cores do tema atual.
        
        Returns:
            Dicionário com as cores do tema
        """
        from ui.themes import LIGHT_THEME, DARK_THEME
        
        theme = self.get("theme", "light")
        return LIGHT_THEME if theme == "light" else DARK_THEME 