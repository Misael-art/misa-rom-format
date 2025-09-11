# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Status Bar
Barra de status da aplicação principal
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class StatusType(Enum):
    """Tipos de status."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"

@dataclass
class StatusMessage:
    """Mensagem de status."""
    text: str
    status_type: StatusType
    timestamp: datetime
    duration: Optional[float] = None  # Duração em segundos (None = permanente)
    progress: Optional[float] = None  # Progresso 0-100
    details: Optional[str] = None

class StatusBar(ttk.Frame):
    """Barra de status da aplicação."""
    
    def __init__(self, parent, config_manager=None, theme_manager=None, **kwargs):
        """
        Inicializa a barra de status.
        
        Args:
            parent: Widget pai
            config_manager: Gerenciador de configurações
            theme_manager: Gerenciador de temas
        """
        super().__init__(parent, **kwargs)
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.parent = parent
        
        # Estado da barra
        self._messages: List[StatusMessage] = []
        self._current_message: Optional[StatusMessage] = None
        self._auto_clear_timer: Optional[threading.Timer] = None
        
        # Variáveis de controle
        self.status_var = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.time_var = tk.StringVar()
        
        # Configurações
        self.max_messages = 100
        self.default_duration = 5.0  # segundos
        
        self._setup_ui()
        self._start_time_update()
        self._apply_theme()
        
        # Mensagem inicial
        self.show_message("Aplicação iniciada", StatusType.INFO)
    
    def _setup_ui(self):
        """Configura a interface da barra."""
        # Frame principal
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Seção de status principal
        self._create_status_section()
        
        # Separador
        separator1 = ttk.Separator(self.main_frame, orient=tk.VERTICAL)
        separator1.pack(side=tk.LEFT, fill=tk.Y, padx=2)
        
        # Seção de progresso
        self._create_progress_section()
        
        # Separador
        separator2 = ttk.Separator(self.main_frame, orient=tk.VERTICAL)
        separator2.pack(side=tk.LEFT, fill=tk.Y, padx=2)
        
        # Seção de informações do sistema
        self._create_system_section()
        
        # Separador
        separator3 = ttk.Separator(self.main_frame, orient=tk.VERTICAL)
        separator3.pack(side=tk.LEFT, fill=tk.Y, padx=2)
        
        # Seção de tempo
        self._create_time_section()
    
    def _create_status_section(self):
        """Cria a seção de status principal."""
        status_frame = ttk.Frame(self.main_frame)
        status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Ícone de status
        self.status_icon = ttk.Label(
            status_frame,
            text="ℹ️",
            font=('TkDefaultFont', 10)
        )
        self.status_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        # Texto de status
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=('TkDefaultFont', 9)
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Botão de detalhes (oculto por padrão)
        self.details_button = ttk.Button(
            status_frame,
            text="📋",
            width=3,
            command=self._show_details
        )
        # Não empacotado por padrão
        
        # Bind para tooltip
        self._bind_tooltip(self.status_label)
    
    def _create_progress_section(self):
        """Cria a seção de progresso."""
        progress_frame = ttk.Frame(self.main_frame)
        progress_frame.pack(side=tk.LEFT, padx=5)
        
        # Barra de progresso
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            length=150,
            mode='determinate'
        )
        self.progress_bar.pack(side=tk.LEFT)
        
        # Texto de progresso
        self.progress_label = ttk.Label(
            progress_frame,
            text="",
            font=('TkDefaultFont', 8),
            width=8
        )
        self.progress_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Oculta por padrão
        progress_frame.pack_forget()
        self.progress_frame = progress_frame
    
    def _create_system_section(self):
        """Cria a seção de informações do sistema."""
        system_frame = ttk.Frame(self.main_frame)
        system_frame.pack(side=tk.LEFT, padx=5)
        
        # Informações do banco
        self.db_icon = ttk.Label(
            system_frame,
            text="🗄️",
            font=('TkDefaultFont', 10)
        )
        self.db_icon.pack(side=tk.LEFT)
        
        self.db_label = ttk.Label(
            system_frame,
            text="DB: OK",
            font=('TkDefaultFont', 8),
            foreground='green'
        )
        self.db_label.pack(side=tk.LEFT, padx=(2, 10))
        
        # Informações de memória
        self.memory_icon = ttk.Label(
            system_frame,
            text="💾",
            font=('TkDefaultFont', 10)
        )
        self.memory_icon.pack(side=tk.LEFT)
        
        self.memory_label = ttk.Label(
            system_frame,
            text="Mem: --",
            font=('TkDefaultFont', 8)
        )
        self.memory_label.pack(side=tk.LEFT, padx=(2, 10))
        
        # Informações de CPU
        self.cpu_icon = ttk.Label(
            system_frame,
            text="⚡",
            font=('TkDefaultFont', 10)
        )
        self.cpu_icon.pack(side=tk.LEFT)
        
        self.cpu_label = ttk.Label(
            system_frame,
            text="CPU: --",
            font=('TkDefaultFont', 8)
        )
        self.cpu_label.pack(side=tk.LEFT, padx=(2, 0))
    
    def _create_time_section(self):
        """Cria a seção de tempo."""
        time_frame = ttk.Frame(self.main_frame)
        time_frame.pack(side=tk.RIGHT, padx=5)
        
        # Ícone de relógio
        clock_icon = ttk.Label(
            time_frame,
            text="🕐",
            font=('TkDefaultFont', 10)
        )
        clock_icon.pack(side=tk.LEFT, padx=(0, 5))
        
        # Texto de tempo
        self.time_label = ttk.Label(
            time_frame,
            textvariable=self.time_var,
            font=('TkDefaultFont', 9)
        )
        self.time_label.pack(side=tk.LEFT)
    
    def _bind_tooltip(self, widget):
        """Adiciona tooltip ao widget."""
        def on_enter(event):
            if self._current_message and self._current_message.details:
                self._show_tooltip(event.widget, self._current_message.details)
        
        def on_leave(event):
            self._hide_tooltip()
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
    def _show_tooltip(self, widget, text):
        """Mostra tooltip."""
        # Implementação simples de tooltip
        try:
            self.tooltip_window = tk.Toplevel()
            self.tooltip_window.wm_overrideredirect(True)
            
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(
                self.tooltip_window,
                text=text,
                background='lightyellow',
                relief='solid',
                borderwidth=1,
                font=('TkDefaultFont', 8)
            )
            label.pack()
        except Exception as e:
            logger.error(f"Erro ao mostrar tooltip: {e}")
    
    def _hide_tooltip(self):
        """Oculta tooltip."""
        try:
            if hasattr(self, 'tooltip_window'):
                self.tooltip_window.destroy()
                del self.tooltip_window
        except Exception as e:
            logger.error(f"Erro ao ocultar tooltip: {e}")
    
    def _start_time_update(self):
        """Inicia atualização do tempo."""
        def update_time():
            while True:
                try:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    self.time_var.set(current_time)
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Erro ao atualizar tempo: {e}")
                    break
        
        time_thread = threading.Thread(target=update_time, daemon=True)
        time_thread.start()
    
    def show_message(self, text: str, status_type: StatusType = StatusType.INFO, 
                    duration: Optional[float] = None, progress: Optional[float] = None,
                    details: Optional[str] = None):
        """Mostra mensagem na barra de status."""
        # Cancela timer anterior
        if self._auto_clear_timer:
            self._auto_clear_timer.cancel()
        
        # Cria nova mensagem
        message = StatusMessage(
            text=text,
            status_type=status_type,
            timestamp=datetime.now(),
            duration=duration or self.default_duration,
            progress=progress,
            details=details
        )
        
        # Adiciona ao histórico
        self._messages.append(message)
        if len(self._messages) > self.max_messages:
            self._messages.pop(0)
        
        # Define como mensagem atual
        self._current_message = message
        
        # Atualiza interface
        self._update_display()
        
        # Programa limpeza automática
        if message.duration and message.duration > 0:
            self._auto_clear_timer = threading.Timer(
                message.duration,
                self._auto_clear
            )
            self._auto_clear_timer.start()
        
        logger.debug(f"Mensagem de status: {text} ({status_type.value})")
    
    def show_progress(self, text: str, progress: float, details: Optional[str] = None):
        """Mostra progresso na barra de status."""
        self.show_message(
            text=text,
            status_type=StatusType.PROGRESS,
            duration=None,  # Não limpa automaticamente
            progress=progress,
            details=details
        )
    
    def hide_progress(self):
        """Oculta barra de progresso."""
        self.progress_frame.pack_forget()
    
    def clear_message(self):
        """Limpa mensagem atual."""
        self._current_message = None
        self.status_var.set("Pronto")
        self.status_icon.config(text="✅")
        self.hide_progress()
        
        # Oculta botão de detalhes
        self.details_button.pack_forget()
    
    def _update_display(self):
        """Atualiza exibição da mensagem atual."""
        if not self._current_message:
            self.clear_message()
            return
        
        message = self._current_message
        
        # Atualiza texto
        self.status_var.set(message.text)
        
        # Atualiza ícone baseado no tipo
        icons = {
            StatusType.INFO: "ℹ️",
            StatusType.SUCCESS: "✅",
            StatusType.WARNING: "⚠️",
            StatusType.ERROR: "❌",
            StatusType.PROGRESS: "⏳"
        }
        self.status_icon.config(text=icons.get(message.status_type, "ℹ️"))
        
        # Atualiza progresso
        if message.status_type == StatusType.PROGRESS and message.progress is not None:
            self.progress_var.set(message.progress)
            self.progress_label.config(text=f"{message.progress:.1f}%")
            self.progress_frame.pack(side=tk.LEFT, padx=5)
        else:
            self.progress_frame.pack_forget()
        
        # Mostra botão de detalhes se necessário
        if message.details:
            self.details_button.pack(side=tk.LEFT, padx=(5, 0))
        else:
            self.details_button.pack_forget()
    
    def _auto_clear(self):
        """Limpa mensagem automaticamente."""
        if self._current_message and self._current_message.duration:
            self.clear_message()
    
    def _show_details(self):
        """Mostra detalhes da mensagem atual."""
        if not self._current_message or not self._current_message.details:
            return
        
        # Cria janela de detalhes
        details_window = tk.Toplevel(self)
        details_window.title("Detalhes")
        details_window.geometry("400x300")
        details_window.transient(self)
        details_window.grab_set()
        
        # Frame principal
        main_frame = ttk.Frame(details_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Título
        title_label = ttk.Label(
            main_frame,
            text=self._current_message.text,
            font=('TkDefaultFont', 10, 'bold')
        )
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Detalhes
        details_text = tk.Text(
            main_frame,
            wrap=tk.WORD,
            height=10,
            font=('TkDefaultFont', 9)
        )
        details_text.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(details_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        details_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=details_text.yview)
        
        # Insere texto
        details_text.insert(tk.END, self._current_message.details)
        details_text.config(state=tk.DISABLED)
        
        # Botão fechar
        close_button = ttk.Button(
            main_frame,
            text="Fechar",
            command=details_window.destroy
        )
        close_button.pack(pady=(10, 0))
        
        # Centraliza janela
        details_window.update_idletasks()
        x = (details_window.winfo_screenwidth() // 2) - (details_window.winfo_width() // 2)
        y = (details_window.winfo_screenheight() // 2) - (details_window.winfo_height() // 2)
        details_window.geometry(f"+{x}+{y}")
    
    def update_database_status(self, status: str, color: str = "green"):
        """Atualiza status do banco de dados."""
        self.db_label.config(text=f"DB: {status}", foreground=color)
    
    def update_memory_usage(self, usage_mb: float):
        """Atualiza uso de memória."""
        if usage_mb < 1024:
            text = f"Mem: {usage_mb:.0f}MB"
        else:
            text = f"Mem: {usage_mb/1024:.1f}GB"
        
        self.memory_label.config(text=text)
    
    def update_cpu_usage(self, usage_percent: float):
        """Atualiza uso de CPU."""
        self.cpu_label.config(text=f"CPU: {usage_percent:.1f}%")
        
        # Muda cor baseado no uso
        if usage_percent > 80:
            color = "red"
        elif usage_percent > 60:
            color = "orange"
        else:
            color = "green"
        
        self.cpu_label.config(foreground=color)
    
    def get_message_history(self) -> List[StatusMessage]:
        """Retorna histórico de mensagens."""
        return self._messages.copy()
    
    def _apply_theme(self):
        """Aplica tema à barra de status."""
        if self.theme_manager:
            try:
                # Aplicar configurações de tema
                theme = self.theme_manager.get_current_theme()
                
                # Configurar cores baseadas no tema
                # Implementar quando theme_manager estiver disponível
                
            except Exception as e:
                logger.error(f"Erro ao aplicar tema: {e}")
    
    def refresh(self):
        """Atualiza a barra de status."""
        self._update_display()
        self._apply_theme()
        logger.debug("Barra de status atualizada")