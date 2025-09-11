#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Frame com Rolagem
Componente de interface que fornece barras de rolagem para conteúdo maior que o espaço disponível
"""

import sys
import tkinter as tk
from tkinter import ttk
import logging

# Logger
logger = logging.getLogger(__name__)

class ScrollableFrame(ttk.Frame):
    """
    Um frame com barras de rolagem horizontal e vertical.
    
    Permite adicionar widgets a um frame interno com barras de rolagem
    para visualizar conteúdo que excede o tamanho visível.
    """
    
    def __init__(self, container, *args, **kwargs):
        """
        Inicializa o frame com rolagem.
        
        Args:
            container: Widget pai
            *args: Argumentos posicionais para ttk.Frame
            **kwargs: Argumentos nomeados para ttk.Frame
        """
        super().__init__(container, *args, **kwargs)
        
        # Cria um canvas
        self.canvas = tk.Canvas(self)
        
        # Cria uma barra de rolagem vertical
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Cria uma barra de rolagem horizontal
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        
        # Configura o canvas para usar as barras
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        # Posiciona as barras de rolagem
        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")
        
        # Posiciona o canvas
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Cria um frame dentro do canvas para conter o conteúdo
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Cria uma janela no canvas para exibir o frame
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        
        # Configura o frame para preencher o canvas
        self.scrollable_frame.bind("<Configure>", self.on_frame_configure)
        
        # Configura o canvas para se ajustar à janela
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Configura rolagem com mouse
        self.scrollable_frame.bind("<Enter>", self.on_enter)
        self.scrollable_frame.bind("<Leave>", self.on_leave)
        
        # Assegura que as barras de rolagem sejam visíveis quando necessário
        self.canvas.bind("<Map>", self.on_canvas_map)
    
    def on_frame_configure(self, event):
        """
        Evento chamado quando o tamanho do frame muda.
        
        Args:
            event: Evento de configuração
        """
        # Atualiza a região de rolagem para corresponder ao tamanho do frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def on_canvas_configure(self, event):
        """
        Evento chamado quando o tamanho do canvas muda.
        
        Args:
            event: Evento de configuração
        """
        # Ajusta o tamanho da janela para corresponder à largura do canvas
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
        # Força a atualização da região de rolagem
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def on_canvas_map(self, event):
        """
        Ajusta as barras de rolagem quando o canvas é exibido.
        
        Args:
            event: Evento de mapeamento
        """
        # Ajusta o tamanho da janela para corresponder à largura do canvas
        self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())
        
        # Atualiza a região de rolagem
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def on_enter(self, event):
        """
        Ativa rolagem por mouse wheel quando o mouse está sobre o frame.
        
        Args:
            event: Evento de entrada do mouse
        """
        try:
            if sys.platform.startswith('win'):
                self.canvas.bind_all("<MouseWheel>", self.on_mousewheel_win)
            else:
                self.canvas.bind_all("<Button-4>", self.on_mousewheel_unix)
                self.canvas.bind_all("<Button-5>", self.on_mousewheel_unix)
        except Exception as e:
            logger.exception("Erro ao configurar evento de mousewheel")
    
    def on_leave(self, event):
        """
        Desativa rolagem por mouse wheel quando o mouse sai do frame.
        
        Args:
            event: Evento de saída do mouse
        """
        try:
            if sys.platform.startswith('win'):
                self.canvas.unbind_all("<MouseWheel>")
            else:
                self.canvas.unbind_all("<Button-4>")
                self.canvas.unbind_all("<Button-5>")
        except Exception as e:
            logger.exception("Erro ao remover evento de mousewheel")
    
    def on_mousewheel_win(self, event):
        """
        Processa rolagem por mouse wheel no Windows.
        
        Args:
            event: Evento de rolagem do mouse
        """
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception as e:
            logger.exception("Erro ao processar rolagem do mouse (Windows)")
    
    def on_mousewheel_unix(self, event):
        """
        Processa rolagem por mouse wheel no Unix.
        
        Args:
            event: Evento de rolagem do mouse
        """
        try:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
        except Exception as e:
            logger.exception("Erro ao processar rolagem do mouse (Unix)")
    
    def update_scrollbars(self):
        """
        Força atualização das barras de rolagem.
        """
        try:
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception as e:
            logger.exception("Erro ao atualizar barras de rolagem")

    def reset_scroll_position(self):
        """
        Reseta a posição da barra de rolagem.
        """
        try:
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
        except Exception as e:
            logger.exception("Erro ao redefinir posição de rolagem")
    
    def get_frame(self):
        """
        Retorna o frame interno rolável.
        
        Returns:
            Frame interno onde os widgets devem ser colocados
        """
        return self.scrollable_frame
    
    def clear_frame(self):
        """
        Remove todos os widgets do frame interno.
        """
        try:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            # Reseta a posição de rolagem
            self.reset_scroll_position()
        except Exception as e:
            logger.exception("Erro ao limpar frame rolável") 