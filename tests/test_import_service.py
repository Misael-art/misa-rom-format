#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testes para o ImportService otimizado
"""
import os
import sys
import time
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from lxml.etree import XMLSyntaxError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.services.import_service import ImportService
from engine.db import UnifiedDatabaseManager as DatabaseManagerV2
from engine.db.pool_config import DatabaseConfig

class TestImportService(unittest.TestCase):
    """Testes para o ImportService."""

    def setUp(self):
        """Configuração inicial."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.config = DatabaseConfig.testing()
        self.db = DatabaseManagerV2(self.config)
        self.db.connect(self.db_path)
        self.service = ImportService(self.db)

    def tearDown(self):
        """Limpeza."""
        self.db.close_all()
        os.rmdir(self.temp_dir)

    def create_test_dat(self, num_games=2):
        """Cria um arquivo DAT de teste."""
        dat_path = os.path.join(self.temp_dir, "test.dat")
        games = []
        for i in range(num_games):
            game = ET.Element("game", name=f"Game {i}")
            description = ET.SubElement(game, "description")
            description.text = f"Description for Game {i}"
            rom = ET.SubElement(game, "rom", name=f"rom{i}.zip", size="1024", crc="00000000", md5="d41d8cd98f00b204e9800998ecf8427e", sha1="da39a3ee5e6b4b0d3255bfef95601890afd80709")
            games.append(game)
        
        root = ET.Element("datafile")
        for game in games:
            root.append(game)
        
        tree = ET.ElementTree(root)
        tree.write(dat_path, encoding="utf-8", xml_declaration=True)
        return dat_path

    def test_import_dat_file_success(self):
        """Testa importação de DAT com sucesso."""
        dat_path = self.create_test_dat(5)
        progress_callback = Mock()
        
        success = self.service.import_dat_file(dat_path, progress_callback)
        self.assertTrue(success)
        self.assertEqual(progress_callback.call_count, 5)

    def test_import_dat_file_invalid_xml(self):
        """Testa importação com XML inválido."""
        invalid_path = os.path.join(self.temp_dir, "invalid.xml")
        with open(invalid_path, "w") as f:
            f.write("<invalid>xml</invalid>")
        
        with self.assertRaises(ValueError):
            self.service.import_dat_file(invalid_path)

    def test_import_dat_file_no_games(self):
        """Testa importação com arquivo sem jogos."""
        dat_path = os.path.join(self.temp_dir, "empty.dat")
        root = ET.Element("datafile")
        tree = ET.ElementTree(root)
        tree.write(dat_path, encoding="utf-8", xml_declaration=True)
        
        with self.assertRaises(ValueError):
            self.service.import_dat_file(dat_path)

    def test_batch_insert_performance(self):
        """Testa performance de batch insert com muitos jogos."""
        dat_path = self.create_test_dat(1000)
        progress_callback = Mock()
        
        start_time = time.time()
        success = self.service.import_dat_file(dat_path, progress_callback)
        end_time = time.time()
        
        self.assertTrue(success)
        self.assertLess(end_time - start_time, 5.0)  # Deve ser rápido com batch

    def test_progress_callback_updates(self):
        """Testa se o callback de progresso é chamado corretamente."""
        dat_path = self.create_test_dat(3)
        progress_callback = Mock()
        
        self.service.import_dat_file(dat_path, progress_callback)
        self.assertEqual(progress_callback.call_count, 3)
        self.assertEqual(progress_callback.call_args_list[0][0][0], 33.333333333333336)  # 1/3
        self.assertEqual(progress_callback.call_args_list[-1][0][0], 100.0)  # 3/3

if __name__ == "__main__":
    unittest.main()