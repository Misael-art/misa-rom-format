' MegaEmu DataBase ROMs Launcher (VBScript)
' Launcher silencioso que executa a aplicação sem mostrar console

Dim objShell, objFSO, scriptPath, appPath, pythonPath

' Criar objetos
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Obter o diretório do script
scriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Configurar variáveis de ambiente
objShell.Environment("Process").Item("TCL_LIBRARY") = "C:\Users\MISAEL\AppData\Local\Programs\Python\Python313\tcl\tcl8.6"
objShell.Environment("Process").Item("TK_LIBRARY") = "C:\Users\MISAEL\AppData\Local\Programs\Python\Python313\tcl\tk8.6"

' Definir o caminho para o Python
pythonPath = "python"

' Verificar se monitor_app.py existe, senão usar app.py
If objFSO.FileExists(scriptPath & "\monitor_app.py") Then
    appPath = scriptPath & "\monitor_app.py"
ElseIf objFSO.FileExists(scriptPath & "\app.py") Then
    appPath = scriptPath & "\app.py"
Else
    MsgBox "Erro: Não foi possível encontrar os arquivos da aplicação." & vbCrLf & _
           "Verifique se monitor_app.py ou app.py existem no diretório.", _
           vbCritical, "MegaEmu Launcher - Erro"
    WScript.Quit
End If

' Executar a aplicação silenciosamente
On Error Resume Next
objShell.Run """" & pythonPath & """ """ & appPath & """", 0, False

If Err.Number <> 0 Then
    MsgBox "Erro ao iniciar a aplicação:" & vbCrLf & Err.Description, _
           vbCritical, "MegaEmu Launcher - Erro"
End If

' Limpar objetos
Set objShell = Nothing
Set objFSO = Nothing