#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Testes do Gerenciador de Temas
Implementa testes unitários para o gerenciador de temas
"""

import unittest
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Importa os módulos a serem testados
from engine.ui import UnifiedThemeManager as ThemeManager
from engine.config.theme_model import ThemeModel, ThemeColorModel
from engine.errors import ThemeError


class TestThemeManager(unittest.TestCase):
    """Testes para o gerenciador de temas."""
    
    def setUp(self):
        """Configura o ambiente de teste."""
        # Cria diretório temporário para temas
        self.test_themes_dir = Path("test_themes")
        self.test_themes_dir.mkdir(exist_ok=True)
        
        # Mock para o gerenciador de configuração
        self.config_mock = MagicMock()
        self.config_mock.set = MagicMock()
        
        # Patch para o ttk.Style
        self.style_patcher = patch('engine.ui.theme_manager_enhanced.ttk.Style')
        self.style_mock = self.style_patcher.start()
        
        # Patch para o ThemeConfigManager
        self.theme_config_patcher = patch('engine.ui.theme_manager_enhanced.ThemeConfigManager')
        self.theme_config_mock = self.theme_config_patcher.start()
        
        # Configura mocks para os gerenciadores de tema
        self.light_manager_mock = MagicMock()
        self.dark_manager_mock = MagicMock()
        
        # Configura retorno dos mocks
        self.theme_config_mock.side_effect = [self.light_manager_mock, self.dark_manager_mock]
        
        # Cria temas de teste
        self.light_theme = ThemeModel(
            name="Test Light",
            type="light",
            colors=ThemeColorModel(
                background="#ffffff",
                foreground="#000000",
                accent="#007acc",
                button="#f0f0f0",
                button_hover="#e0e0e0",
                border="#d0d0d0",
                selection="#cce8ff",
                error="#f44336",
                warning="#ff9800",
                success="#4caf50"
            )
        )
        
        self.dark_theme = ThemeModel(
            name="Test Dark",
            type="dark",
            colors=ThemeColorModel(
                background="#1e1e1e",
                foreground="#ffffff",
                accent="#0078d7",
                button="#333333",
                button_hover="#444444",
                border="#555555",
                selection="#264f78",
                error="#f44336",
                warning="#ff9800",
                success="#4caf50"
            )
        )
        
        # Configura retorno dos gerenciadores de tema
        self.light_manager_mock.get.return_value = self.light_theme
        self.dark_manager_mock.get.return_value = self.dark_theme
        
        # Cria o gerenciador de temas
        self.theme_manager = ThemeManager(config=self.config_mock)
    
    def tearDown(self):
        """Limpa o ambiente após os testes."""
        # Para os patchers
        self.style_patcher.stop()
        self.theme_config_patcher.stop()
        
        # Remove diretório temporário
        if self.test_themes_dir.exists():
            shutil.rmtree(self.test_themes_dir)
    
    def test_init(self):
        """Testa a inicialização do gerenciador de temas."""
        # Verifica se os gerenciadores de tema foram criados corretamente
        self.theme_config_mock.assert_any_call("light", Path("themes"))
        self.theme_config_mock.assert_any_call("dark", Path("themes"))
        
        # Verifica se os temas foram carregados
        self.light_manager_mock.get.assert_called_once()
        self.dark_manager_mock.get.assert_called_once()
        
        # Verifica o tema padrão
        self.assertEqual(self.theme_manager.current_theme, "light")
    
    def test_apply_theme_light(self):
        """Testa a aplicação do tema claro."""
        # Aplica o tema claro
        result = self.theme_manager.apply_theme("light")
        
        # Verifica se o tema foi aplicado com sucesso
        self.assertTrue(result)
        self.assertEqual(self.theme_manager.current_theme, "light")
        
        # Verifica se o método _apply_light_theme foi chamado
        self.style_mock.return_value.theme_use.assert_called_with("default")
        
        # Verifica se a configuração foi atualizada
        self.config_mock.set.assert_called_with("theme", "light")
    
    def test_apply_theme_dark(self):
        """Testa a aplicação do tema escuro."""
        # Aplica o tema escuro
        result = self.theme_manager.apply_theme("dark")
        
        # Verifica se o tema foi aplicado com sucesso
        self.assertTrue(result)
        self.assertEqual(self.theme_manager.current_theme, "dark")
        
        # Verifica se o método _apply_dark_theme foi chamado
        self.style_mock.return_value.theme_use.assert_called_with("default")
        
        # Verifica se a configuração foi atualizada
        self.config_mock.set.assert_called_with("theme", "dark")
    
    def test_apply_theme_invalid(self):
        """Testa a aplicação de um tema inválido."""
        # Aplica um tema inválido
        result = self.theme_manager.apply_theme("invalid")
        
        # Verifica se o tema padrão (light) foi aplicado
        self.assertTrue(result)
        self.assertEqual(self.theme_manager.current_theme, "light")
        
        # Verifica se o método _apply_light_theme foi chamado
        self.style_mock.return_value.theme_use.assert_called_with("default")
    
    def test_get_colors(self):
        """Testa a obtenção das cores do tema atual."""
        # Define o tema atual como light
        self.theme_manager.current_theme = "light"
        self.theme_manager._light_colors = self.light_theme.colors.dict()
        
        # Obtém as cores
        colors = self.theme_manager.get_colors()
        
        # Verifica se as cores estão corretas
        self.assertEqual(colors["background"], "#ffffff")
        self.assertEqual(colors["foreground"], "#000000")
        
        # Define o tema atual como dark
        self.theme_manager.current_theme = "dark"
        self.theme_manager._dark_colors = self.dark_theme.colors.dict()
        
        # Obtém as cores
        colors = self.theme_manager.get_colors()
        
        # Verifica se as cores estão corretas
        self.assertEqual(colors["background"], "#1e1e1e")
        self.assertEqual(colors["foreground"], "#ffffff")
    
    def test_get_color(self):
        """Testa a obtenção de uma cor específica do tema atual."""
        # Define o tema atual como light
        self.theme_manager.current_theme = "light"
        self.theme_manager._light_colors = self.light_theme.colors.dict()
        
        # Obtém uma cor existente
        color = self.theme_manager.get_color("background")
        self.assertEqual(color, "#ffffff")
        
        # Obtém uma cor inexistente
        color = self.theme_manager.get_color("inexistente", "#cccccc")
        self.assertEqual(color, "#cccccc")
    
    def test_update_theme(self):
        """Testa a atualização de um tema."""
        # Configura o mock para o update
        self.light_manager_mock.update.return_value = None
        
        # Atualiza o tema light
        result = self.theme_manager.update_theme("light", {"background": "#eeeeee"})
        
        # Verifica se o tema foi atualizado com sucesso
        self.assertTrue(result)
        
        # Verifica se o método update foi chamado com os parâmetros corretos
        self.light_manager_mock.update.assert_called_once()
    
    def test_update_theme_invalid(self):
        """Testa a atualização de um tema inválido."""
        # Tenta atualizar um tema inválido
        with self.assertRaises(ThemeError):
            self.theme_manager.update_theme("invalid", {"background": "#eeeeee"})
    
    def test_reset_theme(self):
        """Testa a restauração de um tema para as configurações padrão."""
        # Configura o mock para o update
        self.light_manager_mock.update.return_value = None
        
        # Restaura o tema light
        result = self.theme_manager.reset_theme("light")
        
        # Verifica se o tema foi restaurado com sucesso
        self.assertTrue(result)
        
        # Verifica se o método update foi chamado
        self.light_manager_mock.update.assert_called_once()
    
    def test_get_available_themes(self):
        """Testa a obtenção da lista de temas disponíveis."""
        # Obtém a lista de temas
        themes = self.theme_manager.get_available_themes()
        
        # Verifica se a lista contém os temas esperados
        self.assertEqual(len(themes), 2)
        self.assertEqual(themes[0], ("light", "Test Light"))
        self.assertEqual(themes[1], ("dark", "Test Dark"))


if __name__ == "__main__":
    unittest.main()