#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Testes para o DirectoryScanner
"""

import os
import unittest
import tempfile
import shutil
from pathlib import Path
from engine.utils.directory_scanner import DirectoryScanner

class TestDirectoryScanner(unittest.TestCase):
    """Testes para a classe DirectoryScanner"""
    
    def setUp(self):
        """Configura ambiente de teste"""
        # Cria diretório temporário
        self.temp_dir = tempfile.mkdtemp()
        self.scanner = DirectoryScanner()
        
        # Cria alguns arquivos de teste
        self.create_test_files()
        
    def tearDown(self):
        """Limpa ambiente após testes"""
        shutil.rmtree(self.temp_dir)
    
    def create_test_files(self):
        """Cria arquivos para teste"""
        # Arquivo ROM
        with open(os.path.join(self.temp_dir, "test.nes"), "wb") as f:
            f.write(b"NES\x1a" + b"\0" * 1024)
            
        # Arquivo ZIP
        with open(os.path.join(self.temp_dir, "test.zip"), "wb") as f:
            f.write(b"PK\x03\x04" + b"\0" * 1024)
            
        # Subdiretório com arquivo
        sub_dir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "test.iso"), "wb") as f:
            f.write(b"\0" * 1024)
    
    def test_basic_scan(self):
        """Testa escaneamento básico"""
        stats = self.scanner.scan_directory(self.temp_dir)
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats["total_files"], 3)
        self.assertGreater(stats["total_size"], 0)
        self.assertEqual(len(stats["directories"]), 1)
        
    def test_file_patterns(self):
        """Testa filtros de arquivo"""
        # Configura para apenas ROMs
        self.scanner.set_patterns(["*.nes"])
        stats = self.scanner.scan_directory(self.temp_dir)
        
        self.assertEqual(stats["total_files"], 1)
        self.assertTrue(any(f["extension"] == ".nes" for f in stats["files"]))
        
    def test_exclude_patterns(self):
        """Testa padrões de exclusão"""
        self.scanner.set_excluded_patterns(["*.zip"])
        stats = self.scanner.scan_directory(self.temp_dir)
        
        self.assertEqual(stats["total_files"], 2)
        self.assertFalse(any(f["extension"] == ".zip" for f in stats["files"]))
        
    def test_hash_calculation(self):
        """Testa cálculo de hashes"""
        self.scanner.calculate_hashes = True
        self.scanner.hash_algorithms = ["md5", "sha1"]
        stats = self.scanner.scan_directory(self.temp_dir)
        
        for file_info in stats["files"]:
            self.assertIn("md5", file_info)
            self.assertIn("sha1", file_info)
            
    def test_progress_callback(self):
        """Testa callback de progresso"""
        progress_called = False
        
        def progress_callback(progress, message, status):
            nonlocal progress_called
            progress_called = True
            self.assertGreaterEqual(progress, 0)
            self.assertLessEqual(progress, 100)
            return True
            
        self.scanner.scan_directory(self.temp_dir, progress_callback)
        self.assertTrue(progress_called)
        
    def test_cancel_scan(self):
        """Testa cancelamento de escaneamento"""
        def progress_callback(progress, message, status):
            self.scanner.cancel()
            return False
            
        stats = self.scanner.scan_directory(self.temp_dir, progress_callback)
        self.assertTrue(stats.get("cancelled", False))
        
if __name__ == "__main__":
    unittest.main() 