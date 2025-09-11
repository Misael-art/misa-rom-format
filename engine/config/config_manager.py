#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Gerenciador de Configuração
Implementa um gerenciador de configuração com validação usando Pydantic
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union, TypeVar, Generic, Type
from pydantic import BaseModel, ValidationError

from ..errors import ConfigError
from .config_model import AppConfigModel
from .theme_model import ThemeModel, create_light_theme, create_dark_theme

# Configuração de logging
logger = logging.getLogger(__name__)

# Tipo genérico para modelos de configuração
T = TypeVar('T', bound=BaseModel)


class ConfigManager(Generic[T]):
    """
    Gerenciador de configuração genérico com validação usando Pydantic.
    
    Permite carregar, salvar e acessar configurações com validação de tipo
    e valores usando modelos Pydantic.
    """
    
    def __init__(self, config_file: Union[str, Path], model_class: Type[T]):
        """
        Inicializa o gerenciador de configuração.
        
        Args:
            config_file: Caminho para o arquivo de configuração
            model_class: Classe do modelo Pydantic para validação
        """
        self.config_file = Path(config_file)
        self.model_class = model_class
        self._config: Optional[T] = None
        
        # Carrega a configuração
        self.load()
    
    def load(self) -> T:
        """
        Carrega as configurações do arquivo.
        
        Se o arquivo não existir ou for inválido, cria um novo com valores padrão.
        
        Returns:
            Modelo de configuração validado
            
        Raises:
            ConfigError: Se ocorrer um erro ao carregar a configuração
        """
        try:
            # Se já temos uma configuração carregada, retorna
            if self._config is not None:
                return self._config
                
            # Se o arquivo existe, tenta carregar
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                try:
                    # Valida os dados usando o modelo Pydantic
                    self._config = self.model_class(**config_data)
                    logger.info(f"Configuração carregada de {self.config_file}")
                    return self._config
                except ValidationError as e:
                    # Se a validação falhar, registra o erro e usa valores padrão
                    logger.warning(f"Erro de validação na configuração: {str(e)}")
                    self._config = self.model_class()
                    return self._config
            
            # Se o arquivo não existe, cria um novo com valores padrão
            self._config = self.model_class()
            self.save()
            logger.info(f"Arquivo de configuração {self.config_file} não encontrado. Criado com valores padrão.")
            return self._config
            
        except Exception as e:
            # Registra o erro e levanta uma exceção personalizada
            logger.exception(f"Erro ao carregar configuração de {self.config_file}")
            raise ConfigError(f"Erro ao carregar configuração: {str(e)}")
    
    def save(self) -> bool:
        """
        Salva as configurações no arquivo.
        
        Returns:
            True se as configurações foram salvas com sucesso
            
        Raises:
            ConfigError: Se ocorrer um erro ao salvar a configuração
        """
        try:
            # Garante que o diretório existe
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Salva o arquivo
            with open(self.config_file, 'w', encoding='utf-8') as f:
                # Converte o modelo para dicionário e salva como JSON
                json.dump(self._config.dict(), f, indent=2)
                
            logger.info(f"Configuração salva em {self.config_file}")
            return True
            
        except Exception as e:
            # Registra o erro e levanta uma exceção personalizada
            logger.exception(f"Erro ao salvar configuração em {self.config_file}")
            raise ConfigError(f"Erro ao salvar configuração: {str(e)}")
    
    def get(self) -> T:
        """
        Obtém o modelo de configuração.
        
        Returns:
            Modelo de configuração validado
        """
        if self._config is None:
            return self.load()
        return self._config
    
    def update(self, **kwargs) -> T:
        """
        Atualiza a configuração com novos valores.
        
        Args:
            **kwargs: Valores a serem atualizados
            
        Returns:
            Modelo de configuração atualizado
            
        Raises:
            ConfigError: Se ocorrer um erro ao atualizar a configuração
        """
        try:
            # Obtém a configuração atual
            config_dict = self._config.dict() if self._config else {}
            
            # Atualiza com os novos valores
            config_dict.update(kwargs)
            
            # Valida e atualiza o modelo
            self._config = self.model_class(**config_dict)
            
            # Salva a configuração atualizada
            self.save()
            
            return self._config
            
        except ValidationError as e:
            # Se a validação falhar, registra o erro e levanta uma exceção personalizada
            logger.warning(f"Erro de validação ao atualizar configuração: {str(e)}")
            raise ConfigError(f"Erro de validação ao atualizar configuração: {str(e)}")
        except Exception as e:
            # Registra o erro e levanta uma exceção personalizada
            logger.exception("Erro ao atualizar configuração")
            raise ConfigError(f"Erro ao atualizar configuração: {str(e)}")


class AppConfigManager(ConfigManager[AppConfigModel]):
    """
    Gerenciador de configuração da aplicação.
    
    Especialização do ConfigManager para o modelo AppConfigModel.
    """
    
    def __init__(self, config_file: Union[str, Path] = "config.json"):
        """
        Inicializa o gerenciador de configuração da aplicação.
        
        Args:
            config_file: Caminho para o arquivo de configuração
        """
        super().__init__(config_file, AppConfigModel)


class ThemeConfigManager(ConfigManager[ThemeModel]):
    """
    Gerenciador de configuração de temas.
    
    Especialização do ConfigManager para o modelo ThemeModel.
    """
    
    def __init__(self, theme_type: str = "light", themes_dir: Union[str, Path] = "themes"):
        """
        Inicializa o gerenciador de configuração de temas.
        
        Args:
            theme_type: Tipo do tema ("light" ou "dark")
            themes_dir: Diretório para armazenar os temas
        """
        # Garante que o diretório de temas existe
        themes_path = Path(themes_dir)
        themes_path.mkdir(parents=True, exist_ok=True)
        
        # Define o arquivo de configuração baseado no tipo de tema
        config_file = themes_path / f"{theme_type}.json"
        
        super().__init__(config_file, ThemeModel)
        
        # Se não conseguir carregar o tema, cria um padrão
        if self._config is None:
            if theme_type == "dark":
                self._config = create_dark_theme()
            else:
                self._config = create_light_theme()
            self.save()