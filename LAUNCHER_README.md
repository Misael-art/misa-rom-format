# MegaEmu DataBase ROMs - Launchers

Este projeto inclui três tipos diferentes de launchers para facilitar a execução da aplicação com apenas dois cliques:

## 📁 Arquivos de Launcher Disponíveis

### 1. `MegaEmu_Launcher.bat` (Recomendado para Debug)
- **Tipo**: Arquivo batch do Windows
- **Características**:
  - Mostra console com informações de execução
  - Útil para debug e visualização de erros
  - Pausa em caso de erro para permitir leitura
  - Configura automaticamente as variáveis de ambiente TCL/TK

### 2. `MegaEmu_Launcher.pyw` (Recomendado para Uso Normal)
- **Tipo**: Script Python silencioso
- **Características**:
  - Execução silenciosa (sem console)
  - Interface limpa para o usuário final
  - Tratamento de erros com janelas de diálogo
  - Fallback automático entre monitor_app.py e app.py

### 3. `MegaEmu_Launcher.vbs` (Alternativa Silenciosa)
- **Tipo**: Script VBScript
- **Características**:
  - Execução completamente silenciosa
  - Ideal para criar atalhos no desktop
  - Compatível com sistemas Windows antigos
  - Mensagens de erro em janelas de diálogo

## 🚀 Como Usar

### Método 1: Duplo Clique Direto
1. Navegue até a pasta do projeto
2. Dê duplo clique em qualquer um dos launchers:
   - `MegaEmu_Launcher.bat` (com console)
   - `MegaEmu_Launcher.pyw` (silencioso)
   - `MegaEmu_Launcher.vbs` (silencioso)

### Método 2: Criar Atalho no Desktop
1. Clique com o botão direito em um dos launchers
2. Selecione "Criar atalho"
3. Mova o atalho para o desktop
4. (Opcional) Renomeie o atalho para "MegaEmu DataBase ROMs"
5. (Opcional) Altere o ícone clicando com botão direito > Propriedades > Alterar ícone

## ⚙️ Configuração Automática

Todos os launchers configuram automaticamente:
- **TCL_LIBRARY**: Biblioteca Tcl para interface gráfica
- **TK_LIBRARY**: Biblioteca Tk para interface gráfica
- **Diretório de trabalho**: Pasta do projeto

## 🔧 Solução de Problemas

### Erro: "Python não encontrado"
- Verifique se o Python está instalado e no PATH do sistema
- Use o launcher `.bat` para ver mensagens de erro detalhadas

### Erro: "Arquivo não encontrado"
- Verifique se os arquivos `monitor_app.py` ou `app.py` existem na pasta
- Certifique-se de que o launcher está na mesma pasta do projeto

### Erro: "Tkinter não funciona"
- Os launchers configuram automaticamente as bibliotecas TCL/TK
- Se o problema persistir, verifique a instalação do Python

## 📝 Notas Técnicas

- **Prioridade de execução**: Os launchers tentam executar `monitor_app.py` primeiro, depois `app.py` como fallback
- **Variáveis de ambiente**: Configuradas automaticamente para o usuário atual
- **Compatibilidade**: Testado no Windows 10/11 com Python 3.13

## 🎯 Recomendações de Uso

- **Para desenvolvimento**: Use `MegaEmu_Launcher.bat`
- **Para usuário final**: Use `MegaEmu_Launcher.pyw`
- **Para atalhos de desktop**: Use `MegaEmu_Launcher.vbs`