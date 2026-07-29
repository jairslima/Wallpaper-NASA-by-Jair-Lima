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

Primeira versão funcional, com cache resiliente, interface, atualização em segundo plano e agendamento.

## Próximos passos

Validar o comportamento em diferentes configurações de múltiplos monitores e acompanhar eventuais mudanças no serviço APOD.

## Problemas conhecidos

A API pode limitar o uso compartilhado de `DEMO_KEY`. O usuário pode definir `NASA_API_KEY` no ambiente para usar uma chave pessoal.

