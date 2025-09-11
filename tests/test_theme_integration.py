#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Testes de Integração do Gerenciador de Temas
Implementa testes de integração para o gerenciador de temas com o container de injeção de dependências
"""

import unittest
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Importa os módulos a serem testados
from engine.container import CoreContainer
from engine.ui import UnifiedThemeManager as ThemeManager
from engine.config.theme_model import ThemeModel, ThemeColorModel
from engine.errors import ThemeError, ConfigError


class TestThemeIntegration(unittest.TestCase):
    """Testes de integração para o gerenciador de temas."""
    
    def setUp(self):
        """Configura o ambiente de teste."""
        # Cria diretório temporário para temas e configurações
        self.test_dir = Path("test_integration")
        self.test_dir.mkdir(exist_ok=True)
        
        self.themes_dir = self.test_dir / "themes"
        self.themes_dir.mkdir(exist_ok=True)
        
        # Configura o arquivo de configuração de teste
        self.config_file = self.test_dir / "config.json"
        
        # Patch para o ttk.Style
        self.style_patcher = patch('engine.ui.theme_manager_enhanced.ttk.Style')
        self.style_mock = self.style_patcher.start()
        
        # Configura o container com os caminhos de teste
        self.container = CoreContainer()
        self.container.config.override(
            config_file=self.config_file
        )
        
        # Patch para os diretórios de tema
        self.theme_dir_patcher = patch('engine.config.config_manager.Path')
        self.theme_dir_mock = self.theme_dir_patcher.start()
        self.theme_dir_mock.return_value = self.themes_dir
    
    def tearDown(self):
        """Limpa o ambiente após os testes."""
        # Para os patchers
        self.style_patcher.stop()
        self.theme_dir_patcher.stop()
        
        # Remove diretório temporário
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_container_provides_theme_manager(self):
        """Testa se o container fornece corretamente o gerenciador de temas."""
        # Obtém o gerenciador de temas do container
        theme_manager = self.container.theme_manager()
        
        # Verifica se é uma instância de ThemeManager
        self.assertIsInstance(theme_manager, ThemeManager)
    
    def test_theme_manager_uses_config(self):
        """Testa se o gerenciador de temas usa a configuração do container."""
        # Obtém o gerenciador de temas e configuração do container
        theme_manager = self.container.theme_manager()
        config = self.container.config()
        
        # Verifica se o gerenciador de temas está usando a configuração correta
        self.assertEqual(theme_manager.config, config)
    
    def test_apply_theme_updates_config(self):
        """Testa se a aplicação de um tema atualiza a configuração."""
        # Obtém o gerenciador de temas e configuração do container
        theme_manager = self.container.theme_manager()
        config = self.container.config()
        
        # Mock para o método update da configuração
        config.update = MagicMock()
        
        # Aplica o tema escuro
        theme_manager.apply_theme("dark")
        
        # Verifica se a configuração foi atualizada
        config.update.assert_called_with(theme="dark")
    
    def test_error_handling(self):
        """Testa o tratamento de erros na integração."""
        # Obtém o gerenciador de temas do container
        theme_manager = self.container.theme_manager()
        
        # Configura o mock do estilo para lançar uma exceção
        self.style_mock.return_value.configure.side_effect = Exception("Erro de teste")
        
        # Tenta aplicar um tema, o que deve capturar a exceção e retornar False
        result = theme_manager.apply_theme("light")
        self.assertFalse(result)
    
    def test_theme_persistence(self):
        """Testa se as configurações de tema são persistidas corretamente."""
        # Obtém o gerenciador de temas do container
        theme_manager = self.container.theme_manager()
        
        # Aplica o tema escuro
        theme_manager.apply_theme("dark")
        
        # Verifica se o tema atual é o escuro
        self.assertEqual(theme_manager.current_theme, "dark")
        
        # Cria um novo gerenciador de temas para simular reinicialização
        new_theme_manager = self.container.theme_manager()
        
        # Verifica se o tema foi carregado corretamente
        self.assertEqual(new_theme_manager.current_theme, "dark")


if __name__ == "__main__":
    unittest.main()