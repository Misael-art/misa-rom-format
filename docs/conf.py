import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'Mega_Emu_DataBase_ROMs'
copyright = '2025, Misae'
author = 'Misae'

release = '1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
    'sphinx.ext.autodoc_typehints',
]

templates_path = ['_templates']
exclude_patterns = []

language = 'pt_BR'

html_theme = 'alabaster'
html_static_path = ['_static']