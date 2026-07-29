# Wallpaper NASA by Jair Lima

## Objetivo

Aplicativo Windows que consulta diariamente a Astronomy Picture of the Day, APOD, da NASA, baixa a melhor resolução disponível e a define como papel de parede. Em falhas de conexão, API ou download, o último papel de parede válido deve permanecer inalterado.

## Escopo

* Interface gráfica em português.
* Atualização manual e atualização automática diária.
* Busca retroativa de até sete dias quando a publicação atual for um vídeo.
* Download temporário, validação e substituição atômica.
* Cache local em `%LOCALAPPDATA%\Wallpaper NASA by Jair Lima`.
* Persistência de metadados da imagem atual.
* Tarefa do Windows executada diariamente e ao iniciar uma sessão.
* Uso de `DEMO_KEY` por padrão, com suporte opcional à variável local `NASA_API_KEY`.

## Arquitetura

`app.py` contém a integração com a API, o cache, a aplicação do papel de parede, o agendamento e a interface Tkinter. A biblioteca Pillow valida imagens e gera a prévia. A chamada Win32 `SystemParametersInfoW` aplica o papel de parede.

## Dependências

* Python 3.11 ou superior.
* Pillow.
* Windows 10 ou Windows 11.
* API pública APOD da NASA.

## Decisões

* O arquivo atual só é substituído depois que a imagem baixada foi validada.
* Nenhuma falha remove ou modifica a imagem anterior.
* Quando `hdurl` não existe, o aplicativo usa `url`.
* Em dias com vídeo, o aplicativo procura a imagem mais recente dos sete dias anteriores.
* Chaves personalizadas ficam somente em variável de ambiente e nunca no repositório.

## Critérios de aceite

1. Baixar e aplicar uma imagem APOD válida.
2. Manter a imagem anterior quando a conexão estiver indisponível.
3. Não aceitar HTML ou arquivos de imagem corrompidos.
4. Exibir título, data, crédito e estado da atualização.
5. Registrar tarefa automática sem exigir privilégios administrativos.
6. Gerar executável Windows.

## Operação

Execute `python app.py` para abrir a interface. Execute `python app.py --background` para atualizar silenciosamente. Use `python app.py --install-schedule` para instalar a tarefa automática.

