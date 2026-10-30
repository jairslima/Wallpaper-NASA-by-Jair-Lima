# Wallpaper NASA by Jair Lima

Aplicativo desktop para atualizar diariamente o papel de parede do Windows com imagens em alta resolução da NASA, preservando a última imagem quando não há conexão.

## Stack

Python, Tkinter, Pillow, API APOD, API Win32, Registro do Windows e Windows Task Scheduler.

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

Versão inicial concluída, testada, instalada e publicada. O executável está em `C:\Users\jairs\bin`, o atalho está na área de trabalho e a tarefa automática está registrada no Windows. A atualização real pela API APOD foi validada em 29 de julho de 2026. O modo panorâmico foi validado na configuração local de dois monitores 1920 × 1080 lado a lado, produzindo uma composição contínua de 3840 × 1080. O autor confirmou visualmente o alinhamento correto nas duas telas por meio da captura `Captura de tela 2026-07-29 11.19.09.png`.

Repositório: `https://github.com/jairslima/Wallpaper-NASA-by-Jair-Lima`

## Próximos passos

Melhoria opcional para uma versão futura: permitir ajustar manualmente o ponto focal da composição. Também convém acompanhar eventuais mudanças no serviço APOD.

## Problemas conhecidos

A API pode limitar o uso compartilhado de `DEMO_KEY`. O usuário pode definir `NASA_API_KEY` no ambiente para usar uma chave pessoal.

O corte usa o centro geométrico da imagem. Fotografias cujo assunto principal esteja muito deslocado podem se beneficiar de um ajuste manual de ponto focal em uma versão futura.

## Incidente: papel de parede parou de trocar (11-12/08/2026)

Diagnóstico em 12/08/2026: o log (`app.log`) mostrou "read operation timed out" nos dias 10 e 11/08. Testes diretos revelaram que um dos dois servidores por trás de `api.nasa.gov` (`96.127.115.191`) respondia HTTP 503 enquanto o outro (`56.136.115.176`) respondia normalmente, instabilidade transitória do lado da NASA. O Agendador de Tarefas estava funcionando corretamente (`LastRunTime`/`NextRunTime` em dia, sem execuções perdidas); o problema era que `find_latest_image` fazia apenas uma tentativa por execução e desistia na hora se a consulta do dia atual falhasse.

Correção aplicada: nova função `request_json_with_retries` (3 tentativas, 5s de intervalo) usada em `find_latest_image`. Testes adicionados em `tests/test_app.py`. Executável reconstruído e reinstalado em `C:\Users\jairs\bin\`, atalho do Desktop reconfirmado.

## Verificações finais

* Testes automatizados da busca retroativa, validação de imagem e preservação do arquivo anterior aprovados.
* Executável gerado com PyInstaller.
* Atualização automática confirmada no Agendador de Tarefas.
* Modo panorâmico confirmado em dois monitores reais, sem alteração da proporção.
* Continuidade da composição entre as telas confirmada visualmente pelo autor.
* `.gitignore`, licença MIT e ausência de credenciais versionadas verificadas.

## Incidente 30/10/2026: API APOD devolvendo o logo da NASA

- **Sintoma:** o app "atualizava", mas o papel de parede ficava com o logo da NASA (título "NASA Science"), todo dia desde pelo menos 04/10, e o botão manual não mudava nada.
- **Causa:** o `apod.nasa.gov` foi migrado para `science.nasa.gov/apod/`. A API `api.nasa.gov/planetary/apod` passou a ignorar o parâmetro `date` e a devolver `url`/`hdurl` apontando para `nasa-logo@2x.png` (121x102 px), com o texto do dia certo.
- **Correção:** `is_real_photo` rejeita logo/tema; `fetch_feed_items` lê o feed oficial `https://science.nasa.gov/feed/apod-basic/` (campos `apod:hdurl`, `pubDate`) como plano B quando a API falha ou devolve imagem inválida. `update_wallpaper` agora baixa de novo se a URL da imagem mudar ou se o original sumir. 10 testes passando; exe reconstruído e reinstalado em `~/bin`.
- **Segurança:** feed XML recusa DTD/ENTITY e limita 2 MB (bandit B314), com teste.
- **Estado:** foto do dia (Haunting the Cepheus Flare) aplicada e conferida visualmente.
- **Aviso por Telegram (30/10/2026):** no modo agendado (`--background`), `notify_once_a_day` avisa via `telegram_direto.py` (se existir na máquina) quando a troca falha ("falha") ou quando a API devolveu logo e o feed foi usado ("api_degradada"), no máximo 1 aviso por dia por tipo. Antes o app só gravava no `app.log`, e como a API "respondia com sucesso" com a imagem errada, nem o erro existia. Estado em `%LOCALAPPDATA%\Wallpaper NASA by Jair Lima\notify_state.json`.
