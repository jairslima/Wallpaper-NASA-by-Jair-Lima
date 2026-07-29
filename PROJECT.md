# Wallpaper NASA by Jair Lima

Aplicativo desktop para atualizar diariamente o papel de parede do Windows com imagens em alta resolução da NASA, preservando a última imagem quando não há conexão.

## Stack

Python, Tkinter, Pillow, API APOD e Windows Task Scheduler.

## Arquivos

* `app.py`: aplicação completa.
* `tests/test_app.py`: testes da lógica crítica.
* `requirements.txt`: dependências.
* `build.ps1`: geração do executável.
* `SPEC.md`: especificação e decisões.

## Comandos

```powershell
pip install -r requirements.txt
python app.py
python -m unittest discover -s tests -v
pyinstaller --onefile --windowed --name "Wallpaper NASA by Jair Lima" --clean app.py
```

## Estado

Versão inicial concluída, testada, instalada e publicada. O executável está em `C:\Users\jairs\bin`, o atalho está na área de trabalho e a tarefa automática está registrada no Windows. A atualização real pela API APOD foi validada em 29 de julho de 2026.

Repositório: `https://github.com/jairslima/Wallpaper-NASA-by-Jair-Lima`

## Próximos passos

Melhoria opcional para uma versão futura: permitir escolher uma imagem diferente para cada monitor. Também convém acompanhar eventuais mudanças no serviço APOD.

## Problemas conhecidos

A API pode limitar o uso compartilhado de `DEMO_KEY`. O usuário pode definir `NASA_API_KEY` no ambiente para usar uma chave pessoal.

O aplicativo aplica uma única imagem ao papel de parede do Windows. Configurações avançadas com imagens independentes por monitor ainda não estão disponíveis.

## Verificações finais

* Testes automatizados da busca retroativa, validação de imagem e preservação do arquivo anterior aprovados.
* Executável gerado com PyInstaller.
* Atualização automática confirmada no Agendador de Tarefas.
* `.gitignore`, licença MIT e ausência de credenciais versionadas verificadas.
