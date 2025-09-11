#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Testes para o ExportUtils
"""

import os
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from engine.utils.export_utils import ExportUtils, ExportError

class TestExportUtils(unittest.TestCase):
    """Testes para a classe ExportUtils"""
    
    def setUp(self):
        """Configura ambiente de teste"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_data = [
            {
                "id": 1,
                "nome": "Super Mario Bros",
                "sistema": "NES",
                "ano": 1985,
                "tamanho": 32768
            },
            {
                "id": 2,
                "nome": "Sonic the Hedgehog",
                "sistema": "Mega Drive",
                "ano": 1991,
                "tamanho": 524288
            }
        ]
        
    def tearDown(self):
        """Limpa ambiente após testes"""
        shutil.rmtree(self.temp_dir)
    
    def test_export_csv(self):
        """Testa exportação para CSV"""
        file_path = os.path.join(self.temp_dir, "test.csv")
        
        # Testa com colunas padrão
        success = ExportUtils.export_to_csv(self.test_data, file_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(file_path))
        
        # Verifica conteúdo
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Super Mario Bros", content)
            self.assertIn("Sonic the Hedgehog", content)
        
        # Testa com colunas específicas
        columns = ["nome", "sistema"]
        headers = ["Nome do Jogo", "Sistema"]
        success = ExportUtils.export_to_csv(
            self.test_data, 
            file_path,
            columns=columns,
            headers=headers
        )
        self.assertTrue(success)
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Nome do Jogo,Sistema", content)
    
    def test_export_json(self):
        """Testa exportação para JSON"""
        file_path = os.path.join(self.temp_dir, "test.json")
        
        success = ExportUtils.export_to_json(self.test_data, file_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(file_path))
        
        # Verifica se é JSON válido
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["nome"], "Super Mario Bros")
    
    def test_export_xml(self):
        """Testa exportação para XML"""
        file_path = os.path.join(self.temp_dir, "test.xml")
        
        success = ExportUtils.export_to_xml(
            self.test_data, 
            file_path,
            root_element="roms",
            row_element="rom"
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(file_path))
        
        # Verifica conteúdo
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("<roms>", content)
            self.assertIn("<rom>", content)
            self.assertIn("Super Mario Bros", content)
    
    def test_export_html(self):
        """Testa exportação para HTML"""
        file_path = os.path.join(self.temp_dir, "test.html")
        
        success = ExportUtils.export_to_html(
            self.test_data,
            file_path,
            title="Lista de ROMs"
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(file_path))
        
        # Verifica conteúdo
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("<title>Lista de ROMs</title>", content)
            self.assertIn("<table", content)
            self.assertIn("Super Mario Bros", content)
    
    def test_export_markdown(self):
        """Testa exportação para Markdown"""
        file_path = os.path.join(self.temp_dir, "test.md")
        
        success = ExportUtils.export_to_markdown(
            self.test_data,
            file_path,
            title="Lista de ROMs"
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(file_path))
        
        # Verifica conteúdo
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("# Lista de ROMs", content)
            self.assertIn("| Nome ", content)
            self.assertIn("Super Mario Bros", content)
    
    def test_export_yaml(self):
        """Testa exportação para YAML"""
        file_path = os.path.join(self.temp_dir, "test.yaml")
        
        success = ExportUtils.export_to_yaml(self.test_data, file_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(file_path))
        
        # Verifica se é YAML válido
        import yaml
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["nome"], "Super Mario Bros")
    
    def test_invalid_data(self):
        """Testa validação de dados inválidos"""
        file_path = os.path.join(self.temp_dir, "test.csv")
        
        with self.assertRaises(ExportError):
            ExportUtils.export_to_csv(None, file_path)
            
        with self.assertRaises(ExportError):
            ExportUtils.export_to_csv([], file_path)
            
        with self.assertRaises(ExportError):
            ExportUtils.export_to_csv("invalid", file_path)
    
    def test_invalid_file_path(self):
        """Testa validação de caminho de arquivo inválido"""
        with self.assertRaises(ExportError):
            ExportUtils.export_to_csv(self.test_data, "")
            
        with self.assertRaises(ExportError):
            ExportUtils.export_to_csv(self.test_data, "/invalid/path/test.csv")
    
    def test_progress_callback(self):
        """Testa callback de progresso"""
        file_path = os.path.join(self.temp_dir, "test.csv")
        progress_called = False
        
        def progress_callback(progress, current, total):
            nonlocal progress_called
            progress_called = True
            self.assertGreaterEqual(progress, 0)
            self.assertLessEqual(progress, 100)
            return True
            
        ExportUtils.export_to_csv(
            self.test_data,
            file_path,
            progress_callback=progress_callback
        )
        self.assertTrue(progress_called)

if __name__ == "__main__":
    unittest.main() 