#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs - Modelo de Tema
Implementa validação de temas usando Pydantic
"""

import re
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field, validator
from ..errors import ThemeError


class ThemeColorModel(BaseModel):
    """
    Modelo para validação de cores do tema.
    
    Valida que todas as cores necessárias estão presentes e em formato hexadecimal válido.
    """
    background: str = "#ffffff"
    foreground: str = "#000000"
    accent: str = "#007acc"
    button: str = "#f0f0f0"
    button_hover: str = "#e0e0e0"
    border: str = "#d0d0d0"
    selection: str = "#cce8ff"
    error: str = "#f44336"
    warning: str = "#ff9800"
    success: str = "#4caf50"
    
    @validator("*")
    def validate_color(cls, v: str) -> str:
        """
        Valida se a cor está em formato hexadecimal válido.
        
        Args:
            v: Cor em formato hexadecimal
            
        Returns:
            Cor validada
            
        Raises:
            ValueError: Se a cor não estiver em formato válido
        """
        # Remove # se presente e adiciona novamente para padronização
        v = v.lstrip("#")
        
        # Valida formato hexadecimal
        if not re.match(r"^[0-9A-Fa-f]{6}$", v):
            raise ValueError(f"Cor inválida: {v}. Deve estar no formato hexadecimal #RRGGBB")
            
        return f"#{v}"


class ThemeModel(BaseModel):
    """
    Modelo para validação de temas.
    
    Valida as propriedades do tema, incluindo nome, tipo e cores.
    """
    name: str
    type: Literal["light", "dark"] = "light"
    colors: ThemeColorModel
    
    @validator("name")
    def validate_name(cls, v: str) -> str:
        """
        Valida o nome do tema.
        
        Args:
            v: Nome do tema
            
        Returns:
            Nome validado
            
        Raises:
            ValueError: Se o nome estiver vazio
        """
        if not v or not v.strip():
            raise ValueError("O nome do tema não pode estar vazio")
        return v.strip()
    
    class Config:
        """
        Configuração do modelo Pydantic.
        """
        extra = "forbid"  # Não permite campos extras


def create_light_theme() -> ThemeModel:
    """
    Cria um tema claro padrão.
    
    Returns:
        Modelo de tema claro validado
    """
    return ThemeModel(
        name="Light",
        type="light",
        colors=ThemeColorModel(
            background="#ffffff",
            foreground="#000000",
            accent="#007acc",
            button="#f0f0f0",
            button_hover="#e0e0e0",
            border="#d0d0d0",
            selection="#cce8ff",
            error="#f44336",
            warning="#ff9800",
            success="#4caf50"
        )
    )


def create_dark_theme() -> ThemeModel:
    """
    Cria um tema escuro padrão.
    
    Returns:
        Modelo de tema escuro validado
    """
    return ThemeModel(
        name="Dark",
        type="dark",
        colors=ThemeColorModel(
            background="#1e1e1e",
            foreground="#ffffff",
            accent="#0078d7",
            button="#333333",
            button_hover="#444444",
            border="#555555",
            selection="#264f78",
            error="#f44336",
            warning="#ff9800",
            success="#4caf50"
        )
    )