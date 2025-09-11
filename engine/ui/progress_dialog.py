import tkinter as tk
from tkinter import ttk
import logging
from typing import Callable

from engine.ui import UnifiedThemeManager as ThemeManager

class ProgressDialog:
    """Diálogo de progresso."""
    
    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        cancelable: bool = False
    ):
        """
        Inicializa o diálogo.
        
        Args:
            parent: Janela pai
            title: Título do diálogo
            message: Mensagem inicial
            cancelable: Se pode ser cancelado
        """
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centraliza
        window_width = 400
        window_height = 150
        
        screen_width = parent.winfo_screenwidth()
        screen_height = parent.winfo_screenheight()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.window.resizable(False, False)
        
        # Widgets
        self.message_label = ttk.Label(
            self.window,
            text=message,
            wraplength=380
        )
        self.message_label.pack(pady=10)
        
        self.progress_bar = ttk.Progressbar(
            self.window,
            mode="determinate",
            length=380
        )
        self.progress_bar.pack(pady=10)
        
        self.percent_label = ttk.Label(
            self.window,
            text="0%"
        )
        self.percent_label.pack()
        
        if cancelable:
            self.cancel_button = ttk.Button(
                self.window,
                text="Cancelar",
                command=self._on_cancel
            )
            self.cancel_button.pack(pady=10)
            
        # Callback de cancelamento
        self.cancel_callback = None
        
        # Impede fechar
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        
    def update(self, progress: float, message: str = None):
        """
        Atualiza o progresso.
        
        Args:
            progress: Valor de 0 a 100
            message: Nova mensagem opcional
        """
        try:
            # Atualiza barra
            self.progress_bar["value"] = progress
            
            # Atualiza porcentagem
            self.percent_label["text"] = f"{progress:.1f}%"
            
            # Atualiza mensagem
            if message:
                self.message_label["text"] = message
                
            # Atualiza janela
            self.window.update()
            
        except Exception as e:
            logging.error(f"Erro ao atualizar progresso: {str(e)}")
            
    def close(self):
        """Fecha o diálogo."""
        try:
            self.window.grab_release()
            self.window.destroy()
        except Exception as e:
            logging.error(f"Erro ao fechar diálogo: {str(e)}")
            
    def _on_cancel(self):
        """Chamado ao cancelar."""
        try:
            if self.cancel_callback:
                self.cancel_callback()
            self.close()
        except Exception as e:
            logging.error(f"Erro ao cancelar: {str(e)}")
            
    def set_cancel_callback(self, callback: Callable):
        """Define callback de cancelamento."""
        self.cancel_callback = callback 