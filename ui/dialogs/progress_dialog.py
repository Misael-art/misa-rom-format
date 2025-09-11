#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Diálogo de Progresso
Componente para exibir progresso de operações longas
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Optional, Callable, Dict, Any

# Logger
logger = logging.getLogger(__name__)

# Temas
LIGHT_THEME = {
    "bg": "#f5f5f5",
    "fg": "#212121",
    "accent": "#2196F3",
    "highlight": "#E3F2FD",
    "highlight_bg": "#4a6984",
    "highlight_fg": "#ffffff",
    "success": "#4CAF50",
    "warning": "#FFC107",
    "error": "#F44336",
    "border": "#BDBDBD",
}

DARK_THEME = {
    "bg": "#333333",
    "fg": "#f5f5f5",
    "accent": "#90CAF9",
    "highlight": "#1E1E1E",
    "highlight_bg": "#3a3a3a",
    "highlight_fg": "#ffffff",
    "success": "#81C784",
    "warning": "#FFD54F",
    "error": "#E57373",
    "border": "#616161",
}

class ProgressDialog(tk.Toplevel):
    """
    Diálogo de progresso para operações longas.
    
    Exibe uma barra de progresso e mensagens de status durante
    operações de longa duração.
    """
    
    def __init__(
        self, 
        parent: tk.Tk, 
        title: str, 
        message: str, 
        theme: str = "light", 
        determinate: bool = True,
        on_cancel: Optional[Callable] = None,
        **kwargs
    ):
        """
        Inicializa o diálogo de progresso.
        
        Args:
            parent: Widget pai
            title: Título da janela
            message: Mensagem inicial
            theme: Tema a ser usado ("light" ou "dark")
            determinate: Se True, usa modo determinado (0-100%), senão indeterminado
            on_cancel: Função opcional a ser chamada quando o usuário cancela
            **kwargs: Argumentos adicionais para Toplevel
        """
        super().__init__(parent, **kwargs)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Centraliza a janela em relação à janela pai
        window_width = 400
        window_height = 150
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Define o tema
        self.colors = LIGHT_THEME if theme == "light" else DARK_THEME
        
        # Configura o tema
        self.configure(bg=self.colors["bg"])
        
        # Variáveis de controle
        self.message_var = tk.StringVar(value=message)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="")
        self._cancelled = False
        self.on_cancel_callback = on_cancel
        
        # Cria a interface
        self._setup_ui(determinate)
        
        # Protocolo para fechar a janela
        self.protocol("WM_DELETE_WINDOW", self.cancel)
    
    def _setup_ui(self, determinate: bool) -> None:
        """
        Configura a interface do diálogo.
        
        Args:
            determinate: Se True, usa modo determinado, senão indeterminado
        """
        # Frame principal
        main_frame = tk.Frame(self, bg=self.colors["bg"], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Mensagem
        message_label = tk.Label(
            main_frame, 
            textvariable=self.message_var, 
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            font=("Segoe UI", 10)
        )
        message_label.pack(fill=tk.X, pady=(0, 10))
        
        # Barra de progresso
        self.progress_bar = ttk.Progressbar(
            main_frame, 
            variable=self.progress_var, 
            mode="determinate" if determinate else "indeterminate", 
            length=360
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        if not determinate:
            self.progress_bar.start(10)  # Inicia a animação
        
        # Status
        status_label = tk.Label(
            main_frame, 
            textvariable=self.status_var, 
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            font=("Segoe UI", 8)
        )
        status_label.pack(fill=tk.X, pady=(0, 10))
        
        # Botão de cancelar
        self.cancel_button = tk.Button(
            main_frame,
            text="Cancelar",
            command=self.cancel,
            bg=self.colors["button_bg"] if "button_bg" in self.colors else self.colors["bg"],
            fg=self.colors["button_fg"] if "button_fg" in self.colors else self.colors["fg"],
            relief=tk.GROOVE,
            bd=1
        )
        self.cancel_button.pack(side=tk.RIGHT)
    
    def update_progress(self, value: float, message: Optional[str] = None, status: Optional[str] = None) -> bool:
        """
        Atualiza o progresso e as mensagens.
        
        Args:
            value: Valor de progresso (0-100)
            message: Nova mensagem (opcional)
            status: Texto de status (opcional)
            
        Returns:
            False se o usuário cancelou, True caso contrário
        """
        try:
            if self._cancelled:
                return False
                
            # Atualiza o valor de progresso
            self.progress_var.set(value)
            
            # Atualiza a mensagem se fornecida
            if message is not None:
                self.message_var.set(message)
            
            # Atualiza o status se fornecido
            if status is not None:
                self.status_var.set(status)
            
            # Força a atualização da interface
            self.update_idletasks()
            self.update()
            
            return True
        except Exception as e:
            logger.exception("Erro ao atualizar diálogo de progresso")
            return not self._cancelled
    
    def cancel(self) -> None:
        """
        Cancela a operação em progresso.
        """
        self._cancelled = True
        
        # Desabilita o botão de cancelar para prevenir múltiplos cliques
        self.cancel_button.configure(state=tk.DISABLED)
        
        # Atualiza a mensagem
        self.message_var.set("Cancelando operação...")
        
        # Chama o callback de cancelamento, se existir
        if self.on_cancel_callback:
            try:
                self.on_cancel_callback()
            except Exception as e:
                logger.exception("Erro ao executar callback de cancelamento")
    
    def is_cancelled(self) -> bool:
        """
        Verifica se o usuário cancelou a operação.
        
        Returns:
            True se a operação foi cancelada, False caso contrário
        """
        return self._cancelled
    
    def complete(self, message: str = "Operação concluída com sucesso!") -> None:
        """
        Marca a operação como concluída.
        
        Args:
            message: Mensagem de conclusão
        """
        # Garante que o progresso está em 100%
        self.progress_var.set(100.0)
        
        # Atualiza a mensagem
        self.message_var.set(message)
        
        # Altera o botão de cancelar para fechar
        self.cancel_button.configure(text="Fechar", command=self.close)
        
        # Força a atualização da interface
        self.update_idletasks()
    
    def error(self, message: str = "Ocorreu um erro durante a operação.") -> None:
        """
        Marca a operação como falha.
        
        Args:
            message: Mensagem de erro
        """
        # Atualiza a mensagem
        self.message_var.set(message)
        
        # Altera o botão de cancelar para fechar
        self.cancel_button.configure(text="Fechar", command=self.close)
        
        # Força a atualização da interface
        self.update_idletasks()
    
    def close(self) -> None:
        """
        Fecha o diálogo.
        """
        self.grab_release()
        self.destroy()
    
    def wait_for_completion(self, check_interval: int = 100) -> bool:
        """
        Aguarda até que a operação seja concluída ou cancelada.
        
        Args:
            check_interval: Intervalo em milissegundos para verificação
            
        Returns:
            True se a operação foi concluída, False se foi cancelada
        """
        def check_status():
            if not self._cancelled and self.winfo_exists():
                self.after(check_interval, check_status)
        
        check_status()
        self.wait_window()
        return not self._cancelled 