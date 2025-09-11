# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Enhanced Config Manager
Gerenciador de configurações melhorado com suporte a validação e callbacks
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigType(Enum):
    """Tipos de configuração suportados."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"

@dataclass
class ConfigSchema:
    """Schema de validação para configurações."""
    key: str
    config_type: ConfigType
    default_value: Any
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    required: bool = False
    description: str = ""
    validator: Optional[Callable[[Any], bool]] = None

class EnhancedConfigManager:
    """Gerenciador de configurações melhorado."""
    
    def __init__(self, config_file: str = "config.json", auto_save: bool = True):
        """
        Inicializa o gerenciador de configurações.
        
        Args:
            config_file: Caminho para o arquivo de configuração
            auto_save: Se deve salvar automaticamente após mudanças
        """
        self.config_file = Path(config_file)
        self.auto_save = auto_save
        self._config: Dict[str, Any] = {}
        self._schemas: Dict[str, ConfigSchema] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._backup_count = 5
        
        # Registra schemas padrão
        self._register_default_schemas()
        
        # Carrega configurações
        self.load()
    
    def _register_default_schemas(self):
        """Registra schemas padrão para validação."""
        schemas = [
            # Interface
            ConfigSchema("theme", ConfigType.STRING, "light", 
                        allowed_values=["light", "dark"], 
                        description="Tema da interface"),
            ConfigSchema("show_welcome", ConfigType.BOOLEAN, True,
                        description="Mostrar tela de boas-vindas"),
            ConfigSchema("show_navigation", ConfigType.BOOLEAN, True,
                        description="Mostrar painel de navegação"),
            ConfigSchema("window_size", ConfigType.STRING, "1024x768",
                        allowed_values=["800x600", "1024x768", "1280x720", "1366x768", "1920x1080"],
                        description="Tamanho da janela"),
            
            # Logging
            ConfigSchema("log_level", ConfigType.STRING, "INFO",
                        allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        description="Nível de log"),
            ConfigSchema("log_file", ConfigType.STRING, "app.log",
                        description="Arquivo de log"),
            
            # Banco de dados
            ConfigSchema("db_timeout", ConfigType.INTEGER, 30,
                        min_value=5, max_value=300,
                        description="Timeout de conexão em segundos"),
            ConfigSchema("db_max_connections", ConfigType.INTEGER, 5,
                        min_value=1, max_value=50,
                        description="Máximo de conexões simultâneas"),
            ConfigSchema("db_pool_size", ConfigType.INTEGER, 10,
                        min_value=1, max_value=100,
                        description="Tamanho do pool de conexões"),
            ConfigSchema("auto_save", ConfigType.BOOLEAN, True,
                        description="Salvamento automático"),
            
            # Importação
            ConfigSchema("import_batch_size", ConfigType.INTEGER, 1000,
                        min_value=100, max_value=10000,
                        description="Tamanho do lote de importação"),
            ConfigSchema("last_import_dir", ConfigType.STRING, "",
                        description="Último diretório de importação"),
            ConfigSchema("last_roms_dir", ConfigType.STRING, "",
                        description="Último diretório de ROMs"),
            ConfigSchema("import_threads", ConfigType.INTEGER, 4,
                        min_value=1, max_value=16,
                        description="Número de threads para importação"),
            
            # Backup
            ConfigSchema("backup_enabled", ConfigType.BOOLEAN, True,
                        description="Backup automático habilitado"),
            ConfigSchema("backup_interval", ConfigType.INTEGER, 24,
                        min_value=1, max_value=168,
                        description="Intervalo de backup em horas"),
            ConfigSchema("backup_count", ConfigType.INTEGER, 5,
                        min_value=1, max_value=20,
                        description="Número de backups a manter"),
            
            # Performance
            ConfigSchema("cache_size", ConfigType.INTEGER, 1000,
                        min_value=100, max_value=10000,
                        description="Tamanho do cache"),
            ConfigSchema("memory_limit", ConfigType.INTEGER, 512,
                        min_value=128, max_value=4096,
                        description="Limite de memória em MB"),
            
            # Segurança
            ConfigSchema("enable_encryption", ConfigType.BOOLEAN, False,
                        description="Habilitar criptografia"),
            ConfigSchema("session_timeout", ConfigType.INTEGER, 3600,
                        min_value=300, max_value=86400,
                        description="Timeout de sessão em segundos"),
        ]
        
        for schema in schemas:
            self._schemas[schema.key] = schema
    
    def register_schema(self, schema: ConfigSchema):
        """Registra um schema de configuração."""
        with self._lock:
            self._schemas[schema.key] = schema
            logger.debug(f"Schema registrado: {schema.key}")
    
    def register_callback(self, key: str, callback: Callable[[str, Any, Any], None]):
        """
        Registra callback para mudanças de configuração.
        
        Args:
            key: Chave da configuração
            callback: Função chamada quando a configuração muda (key, old_value, new_value)
        """
        with self._lock:
            if key not in self._callbacks:
                self._callbacks[key] = []
            self._callbacks[key].append(callback)
            logger.debug(f"Callback registrado para: {key}")
    
    def unregister_callback(self, key: str, callback: Callable):
        """Remove callback de configuração."""
        with self._lock:
            if key in self._callbacks and callback in self._callbacks[key]:
                self._callbacks[key].remove(callback)
                logger.debug(f"Callback removido para: {key}")
    
    def _validate_value(self, key: str, value: Any) -> bool:
        """Valida um valor de configuração."""
        if key not in self._schemas:
            logger.warning(f"Schema não encontrado para: {key}")
            return True
        
        schema = self._schemas[key]
        
        # Validação de tipo
        if schema.config_type == ConfigType.STRING and not isinstance(value, str):
            return False
        elif schema.config_type == ConfigType.INTEGER and not isinstance(value, int):
            return False
        elif schema.config_type == ConfigType.FLOAT and not isinstance(value, (int, float)):
            return False
        elif schema.config_type == ConfigType.BOOLEAN and not isinstance(value, bool):
            return False
        elif schema.config_type == ConfigType.LIST and not isinstance(value, list):
            return False
        elif schema.config_type == ConfigType.DICT and not isinstance(value, dict):
            return False
        
        # Validação de range
        if schema.min_value is not None and value < schema.min_value:
            return False
        if schema.max_value is not None and value > schema.max_value:
            return False
        
        # Validação de valores permitidos
        if schema.allowed_values is not None and value not in schema.allowed_values:
            return False
        
        # Validador customizado
        if schema.validator is not None and not schema.validator(value):
            return False
        
        return True
    
    def _notify_callbacks(self, key: str, old_value: Any, new_value: Any):
        """Notifica callbacks sobre mudança de configuração."""
        if key in self._callbacks:
            for callback in self._callbacks[key]:
                try:
                    callback(key, old_value, new_value)
                except Exception as e:
                    logger.error(f"Erro em callback para {key}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor de configuração."""
        with self._lock:
            if key in self._config:
                return self._config[key]
            
            # Usa valor padrão do schema se disponível
            if key in self._schemas:
                return self._schemas[key].default_value
            
            return default
    
    def set(self, key: str, value: Any, validate: bool = True) -> bool:
        """
        Define valor de configuração.
        
        Args:
            key: Chave da configuração
            value: Valor a ser definido
            validate: Se deve validar o valor
            
        Returns:
            True se o valor foi definido com sucesso
        """
        with self._lock:
            # Validação
            if validate and not self._validate_value(key, value):
                logger.error(f"Valor inválido para {key}: {value}")
                return False
            
            old_value = self._config.get(key)
            self._config[key] = value
            
            # Notifica callbacks
            if old_value != value:
                self._notify_callbacks(key, old_value, value)
            
            # Auto-save
            if self.auto_save:
                try:
                    self.save()
                except Exception as e:
                    logger.error(f"Erro no auto-save: {e}")
            
            logger.debug(f"Configuração definida: {key} = {value}")
            return True
    
    def update(self, config_dict: Dict[str, Any], validate: bool = True) -> Dict[str, bool]:
        """
        Atualiza múltiplas configurações.
        
        Args:
            config_dict: Dicionário com configurações
            validate: Se deve validar os valores
            
        Returns:
            Dicionário com resultado de cada configuração
        """
        results = {}
        
        with self._lock:
            for key, value in config_dict.items():
                results[key] = self.set(key, value, validate)
        
        return results
    
    def delete(self, key: str) -> bool:
        """Remove configuração."""
        with self._lock:
            if key in self._config:
                old_value = self._config[key]
                del self._config[key]
                
                # Notifica callbacks
                self._notify_callbacks(key, old_value, None)
                
                # Auto-save
                if self.auto_save:
                    try:
                        self.save()
                    except Exception as e:
                        logger.error(f"Erro no auto-save: {e}")
                
                logger.debug(f"Configuração removida: {key}")
                return True
            
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """Retorna todas as configurações."""
        with self._lock:
            return self._config.copy()
    
    def get_schema(self, key: str) -> Optional[ConfigSchema]:
        """Retorna schema de uma configuração."""
        return self._schemas.get(key)
    
    def get_all_schemas(self) -> Dict[str, ConfigSchema]:
        """Retorna todos os schemas."""
        return self._schemas.copy()
    
    def validate_all(self) -> Dict[str, bool]:
        """Valida todas as configurações."""
        results = {}
        
        with self._lock:
            for key, value in self._config.items():
                results[key] = self._validate_value(key, value)
        
        return results
    
    def reset_to_defaults(self, keys: Optional[List[str]] = None):
        """Reseta configurações para valores padrão."""
        with self._lock:
            if keys is None:
                keys = list(self._schemas.keys())
            
            for key in keys:
                if key in self._schemas:
                    old_value = self._config.get(key)
                    default_value = self._schemas[key].default_value
                    self._config[key] = default_value
                    
                    # Notifica callbacks
                    if old_value != default_value:
                        self._notify_callbacks(key, old_value, default_value)
            
            # Auto-save
            if self.auto_save:
                try:
                    self.save()
                except Exception as e:
                    logger.error(f"Erro no auto-save: {e}")
            
            logger.info(f"Configurações resetadas: {keys}")
    
    def backup(self, backup_file: Optional[str] = None) -> str:
        """Cria backup das configurações."""
        if backup_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self.config_file.stem}_backup_{timestamp}.json"
        
        backup_path = self.config_file.parent / backup_file
        
        with self._lock:
            try:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Backup criado: {backup_path}")
                return str(backup_path)
                
            except Exception as e:
                logger.error(f"Erro ao criar backup: {e}")
                raise
    
    def restore(self, backup_file: str):
        """Restaura configurações de backup."""
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Arquivo de backup não encontrado: {backup_file}")
        
        with self._lock:
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_config = json.load(f)
                
                # Valida configurações do backup
                invalid_configs = []
                for key, value in backup_config.items():
                    if not self._validate_value(key, value):
                        invalid_configs.append(key)
                
                if invalid_configs:
                    logger.warning(f"Configurações inválidas no backup: {invalid_configs}")
                
                # Aplica configurações válidas
                old_config = self._config.copy()
                self._config = backup_config
                
                # Notifica callbacks para mudanças
                for key, new_value in backup_config.items():
                    old_value = old_config.get(key)
                    if old_value != new_value:
                        self._notify_callbacks(key, old_value, new_value)
                
                # Auto-save
                if self.auto_save:
                    self.save()
                
                logger.info(f"Configurações restauradas de: {backup_file}")
                
            except Exception as e:
                logger.error(f"Erro ao restaurar backup: {e}")
                raise
    
    def load(self):
        """Carrega configurações do arquivo."""
        if not self.config_file.exists():
            logger.info(f"Arquivo de configuração não encontrado: {self.config_file}")
            # Cria configurações padrão
            self._create_default_config()
            return
        
        with self._lock:
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # Valida configurações carregadas
                valid_config = {}
                for key, value in loaded_config.items():
                    if self._validate_value(key, value):
                        valid_config[key] = value
                    else:
                        logger.warning(f"Configuração inválida ignorada: {key} = {value}")
                
                self._config = valid_config
                logger.info(f"Configurações carregadas: {self.config_file}")
                
            except Exception as e:
                logger.error(f"Erro ao carregar configurações: {e}")
                # Cria configurações padrão em caso de erro
                self._create_default_config()
    
    def save(self):
        """Salva configurações no arquivo."""
        # Cria backup antes de salvar
        if self.config_file.exists():
            try:
                self._rotate_backups()
            except Exception as e:
                logger.warning(f"Erro ao criar backup automático: {e}")
        
        with self._lock:
            try:
                # Cria diretório se não existir
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Salva configurações
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
                
                logger.debug(f"Configurações salvas: {self.config_file}")
                
            except Exception as e:
                logger.error(f"Erro ao salvar configurações: {e}")
                raise
    
    def _create_default_config(self):
        """Cria configurações padrão."""
        with self._lock:
            self._config = {}
            
            # Adiciona valores padrão dos schemas
            for key, schema in self._schemas.items():
                self._config[key] = schema.default_value
            
            # Salva configurações padrão
            if self.auto_save:
                try:
                    self.save()
                except Exception as e:
                    logger.error(f"Erro ao salvar configurações padrão: {e}")
            
            logger.info("Configurações padrão criadas")
    
    def _rotate_backups(self):
        """Rotaciona backups automáticos."""
        backup_dir = self.config_file.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Lista backups existentes
        backup_pattern = f"{self.config_file.stem}_auto_*.json"
        existing_backups = sorted(backup_dir.glob(backup_pattern))
        
        # Remove backups antigos
        while len(existing_backups) >= self._backup_count:
            oldest_backup = existing_backups.pop(0)
            oldest_backup.unlink()
            logger.debug(f"Backup antigo removido: {oldest_backup}")
        
        # Cria novo backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{self.config_file.stem}_auto_{timestamp}.json"
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Backup automático criado: {backup_file}")
            
        except Exception as e:
            logger.error(f"Erro ao criar backup automático: {e}")
    
    def export_config(self, export_file: str, keys: Optional[List[str]] = None):
        """Exporta configurações para arquivo."""
        export_path = Path(export_file)
        
        with self._lock:
            if keys is None:
                export_data = self._config.copy()
            else:
                export_data = {k: v for k, v in self._config.items() if k in keys}
            
            try:
                export_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Configurações exportadas: {export_file}")
                
            except Exception as e:
                logger.error(f"Erro ao exportar configurações: {e}")
                raise
    
    def import_config(self, import_file: str, merge: bool = True, validate: bool = True):
        """Importa configurações de arquivo."""
        import_path = Path(import_file)
        
        if not import_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {import_file}")
        
        with self._lock:
            try:
                with open(import_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
                
                if not merge:
                    # Substitui todas as configurações
                    old_config = self._config.copy()
                    self._config = {}
                else:
                    old_config = self._config.copy()
                
                # Aplica configurações importadas
                invalid_configs = []
                for key, value in import_data.items():
                    if validate and not self._validate_value(key, value):
                        invalid_configs.append(key)
                        continue
                    
                    old_value = self._config.get(key)
                    self._config[key] = value
                    
                    # Notifica callbacks
                    if old_value != value:
                        self._notify_callbacks(key, old_value, value)
                
                if invalid_configs:
                    logger.warning(f"Configurações inválidas ignoradas: {invalid_configs}")
                
                # Auto-save
                if self.auto_save:
                    self.save()
                
                logger.info(f"Configurações importadas: {import_file}")
                
            except Exception as e:
                logger.error(f"Erro ao importar configurações: {e}")
                raise
    
    def get_config_info(self) -> Dict[str, Any]:
        """Retorna informações sobre as configurações."""
        with self._lock:
            return {
                "config_file": str(self.config_file),
                "auto_save": self.auto_save,
                "total_configs": len(self._config),
                "total_schemas": len(self._schemas),
                "total_callbacks": sum(len(callbacks) for callbacks in self._callbacks.values()),
                "file_exists": self.config_file.exists(),
                "file_size": self.config_file.stat().st_size if self.config_file.exists() else 0,
                "last_modified": datetime.fromtimestamp(self.config_file.stat().st_mtime).isoformat() if self.config_file.exists() else None
            }