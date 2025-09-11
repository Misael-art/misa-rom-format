#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MegaEmu DataBase ROMs - Diálogos
Diálogos modais da interface gráfica
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)

class ProgressDialog:
    """Diálogo de progresso com barra de progresso."""
    
    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        theme: str = "light"
    ):
        """
        Inicializa o diálogo.
        
        Args:
            parent: Janela pai
            title: Título do diálogo
            message: Mensagem inicial
            theme: Tema da interface (light/dark)
        """
        self.parent = parent
        self.title = title
        self.message = message
        self.theme = theme
        
        # Cria janela
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centraliza
        window_width = 400
        window_height = 150
        
        screen_width = parent.winfo_screenwidth()
        screen_height = parent.winfo_screenheight()
        
        x = parent.winfo_x() + (parent.winfo_width() - window_width) // 2
        y = parent.winfo_y() + (parent.winfo_height() - window_height) // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.window.resizable(False, False)
        
        # Cria widgets
        self.create_widgets()
        
        # Aplica tema
        self.apply_theme()
        
        # Atualiza
        self.window.update()
    
    def create_widgets(self):
        """Cria os widgets do diálogo."""
        # Frame principal
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Mensagem
        self.message_label = ttk.Label(
            self.main_frame,
            text=self.message,
            wraplength=380,
            justify="left"
        )
        self.message_label.pack(fill="x", pady=(0, 10))
        
        # Barra de progresso
        self.progress = ttk.Progressbar(
            self.main_frame,
            mode="determinate",
            length=380
        )
        self.progress.pack(fill="x", pady=(0, 10))
        
        # Status
        self.status_label = ttk.Label(
            self.main_frame,
            text="0%",
            anchor="center"
        )
        self.status_label.pack(fill="x")
        
        # Botão cancelar
        self.cancel_button = ttk.Button(
            self.main_frame,
            text="Cancelar",
            command=self.cancel
        )
        self.cancel_button.pack(side="right")
        
        # Flag de cancelamento
        self.cancelled = False
    
    def apply_theme(self):
        """Aplica o tema atual."""
        if self.theme == "dark":
            style = ttk.Style()
            style.configure(
                "TFrame",
                background="#2d2d2d"
            )
            style.configure(
                "TLabel",
                background="#2d2d2d",
                foreground="#ffffff"
            )
            style.configure(
                "TButton",
                background="#404040",
                foreground="#ffffff"
            )
            
            self.window.configure(bg="#2d2d2d")
    
    def update_progress(self, value: float, message: str = None):
        """
        Atualiza o progresso.
        
        Args:
            value: Valor do progresso (0-100)
            message: Nova mensagem (opcional)
        """
        if message:
            self.message_label.config(text=message)
        
        self.progress["value"] = value
        self.status_label.config(text=f"{value:.1f}%")
        self.window.update()
    
    def complete(self, message: str = None):
        """
        Finaliza o diálogo.
        
        Args:
            message: Mensagem final (opcional)
        """
        if message:
            self.message_label.config(text=message)
        
        self.progress["value"] = 100
        self.status_label.config(text="100%")
        self.cancel_button.config(text="Fechar")
        self.window.update()
    
    def cancel(self):
        """Cancela a operação."""
        self.cancelled = True
        self.window.destroy()
    
    def was_cancelled(self) -> bool:
        """Retorna se foi cancelado."""
        return self.cancelled 