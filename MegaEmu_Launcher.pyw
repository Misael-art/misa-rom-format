#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MegaEmu DataBase ROMs Launcher
Launcher silencioso para a aplicação MegaEmu DataBase ROMs
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Função principal do launcher"""
    try:
        # Obter o diretório do script
        script_dir = Path(__file__).parent.absolute()
        
        # Configurar variáveis de ambiente para Tcl/Tk
        os.environ['TCL_LIBRARY'] = r'C:\Users\MISAEL\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'
        os.environ['TK_LIBRARY'] = r'C:\Users\MISAEL\AppData\Local\Programs\Python\Python313\tcl\tk8.6'
        
        # Caminho para o monitor_app.py
        monitor_script = script_dir / 'monitor_app.py'
        
        if not monitor_script.exists():
            # Fallback para app.py se monitor_app.py não existir
            monitor_script = script_dir / 'app.py'
        
        if monitor_script.exists():
            # Executar a aplicação usando pythonw para não mostrar console
            subprocess.Popen([
                sys.executable,
                str(monitor_script)
            ], cwd=str(script_dir))
        else:
            # Se nenhum script for encontrado, mostrar erro
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()  # Esconder a janela principal
            messagebox.showerror(
                "Erro", 
                "Não foi possível encontrar os arquivos da aplicação.\n"
                "Verifique se monitor_app.py ou app.py existem no diretório."
            )
            root.destroy()
            
    except Exception as e:
        # Em caso de erro, mostrar mensagem
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Erro no Launcher", 
                f"Erro ao iniciar a aplicação:\n{str(e)}"
            )
            root.destroy()
        except:
            # Se até mesmo o tkinter falhar, usar print
            print(f"Erro ao iniciar a aplicação: {e}")

if __name__ == '__main__':
    main()