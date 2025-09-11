@echo off
REM MegaEmu DataBase ROMs Launcher
REM Este launcher configura o ambiente e executa a aplicação

echo ========================================
echo    MegaEmu DataBase ROMs Launcher
echo ========================================
echo.
echo Iniciando aplicação...
echo.

REM Navegar para o diretório da aplicação
cd /d "%~dp0"

REM Configurar variáveis de ambiente para Tcl/Tk
set TCL_LIBRARY=C:\Users\MISAEL\AppData\Local\Programs\Python\Python313\tcl\tcl8.6
set TK_LIBRARY=C:\Users\MISAEL\AppData\Local\Programs\Python\Python313\tcl\tk8.6

REM Executar a aplicação usando o monitor_app.py
python monitor_app.py

REM Pausar para mostrar qualquer mensagem de erro
if errorlevel 1 (
    echo.
    echo Erro ao executar a aplicação!
    echo Pressione qualquer tecla para fechar...
    pause >nul
)

exit