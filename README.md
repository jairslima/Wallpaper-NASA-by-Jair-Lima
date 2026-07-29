# Wallpaper NASA by Jair Lima

Atualiza diariamente o papel de parede do Windows com a imagem astronômica do dia da NASA. Se a conexão falhar, a imagem anterior permanece intacta.

## Uso

1. Abra `Wallpaper NASA by Jair Lima.exe`.
2. Clique em `Atualizar agora`.
3. Mantenha a opção de atualização automática ativada.

O aplicativo usa a chave de demonstração pública da NASA. Opcionalmente, defina `NASA_API_KEY` como variável de ambiente para usar sua própria chave.

## Desenvolvimento

```powershell
pip install -r requirements.txt
python app.py
python -m unittest discover -s tests -v
```

