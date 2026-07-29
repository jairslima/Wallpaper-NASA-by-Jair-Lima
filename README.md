# Wallpaper NASA by Jair Lima

Atualiza diariamente o papel de parede do Windows com a imagem astronômica do dia da NASA. Se a conexão falhar, a imagem anterior permanece intacta.

Em computadores com vários monitores, o aplicativo cria uma composição panorâmica contínua. A imagem é ampliada proporcionalmente, centralizada e cortada somente nas bordas excedentes, sem deformação.

## Uso

1. Abra `Wallpaper NASA by Jair Lima.exe`.
2. Clique em `Atualizar agora`.
3. Mantenha a opção de atualização automática ativada.

O aplicativo usa a chave de demonstração pública da NASA. Opcionalmente, defina `NASA_API_KEY` como variável de ambiente para usar sua própria chave.

## Comportamento sem conexão

O novo arquivo somente substitui o anterior depois de ser completamente baixado e validado como imagem. Se a NASA, a conexão ou o download falhar, o aplicativo reaplica o último arquivo válido do cache local.

## Automação no Windows

A tarefa `Wallpaper NASA by Jair Lima` executa a atualização ao entrar no Windows e diariamente às 9h. O cache e os metadados ficam em `%LOCALAPPDATA%\Wallpaper NASA by Jair Lima`.

## Distribuição

O executável local fica em `C:\Users\jairs\bin\Wallpaper NASA by Jair Lima.exe`. O projeto é distribuído sob a licença MIT.

## Desenvolvimento

```powershell
pip install -r requirements.txt
python app.py
python -m unittest discover -s tests -v
```
