"""
Pacote para interface gráfica.
"""

# Importa o gerenciador unificado como padrão
from .unified_theme_manager import UnifiedThemeManager

# Mantém compatibilidade com código existente
ThemeManager = UnifiedThemeManager

# Importa implementações legadas para referência (deprecated)
from .theme_manager import ThemeManager as LegacyThemeManager
try:
    from .theme_manager_enhanced import ThemeManager as LegacyThemeManagerEnhanced
except ImportError:
    LegacyThemeManagerEnhanced = None
from .progress_dialog import ProgressDialog
from .main_window import MainWindow

__all__ = [
    'ThemeManager',
    'ProgressDialog',
    'MainWindow'
]