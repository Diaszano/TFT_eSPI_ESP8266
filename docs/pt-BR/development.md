[English](../en/development.md) | Português (Brasil)

# Desenvolvimento

## Alvos do Make

Use Python 3.14.7 para as ferramentas de desenvolvimento. Instale as ferramentas com versões e hashes fixados usando `python -m pip install --require-hashes -r scripts/requirements-dev.txt`; o build usa a plataforma ESP8266 4.2.1 e acompanha entradas aninhadas da biblioteca e dos exemplos para que inclusões, alterações e remoções invalidem builds em cache.

| Alvo | Finalidade |
| --- | --- |
| `make build` | Compila todos os exemplos selecionados. |
| `make build-<Name>` | Compila um exemplo, como `make build-Colour_Test`. |
| `make upload EX=<Name> PORT=<port>` | Envia um exemplo à placa. |
| `make uploadfs EX=<Name> PORT=<port>` | Envia os dados do sistema de arquivos de um exemplo. |
| `make monitor PORT=<port>` | Abre o monitor serial. |
| `make clean` | Remove os arquivos gerados de build. |
| `make docs-check` | Verifica pares de documentação, links e referências a APIs removidas. |
| `make docs` | Executa as verificações da documentação e gera a referência da API. |
| `make help` | Lista os alvos disponíveis. |

A CI compila os exemplos selecionados com PlatformIO. O workflow de documentação verifica e gera os arquivos; o job de publicação no Pages executa somente em pushes para `main`.

`make size-check` falha se o uso estático de flash ou RAM aumentar ou se o perfil de build mudar. O total de RAM inclui dados inicializados, dados somente leitura e BSS; ele não mede o heap usado em tempo de execução por sprites, fontes ou outras alocações.

## Estrutura da biblioteca Arduino

Arduino e PlatformIO compilam `src/TFT_eSPI.cpp` como a única unidade de tradução de produção da biblioteca. Sprite, fonte suave, driver e dados das fontes embutidas são fragmentos incluídos; mantenha-os como `.inc` ou headers, nunca como arquivos `.cpp`/`.c` compilados separadamente. O `User_Setup.h` editável permanece na raiz do pacote.

## Adicionar um exemplo

Crie `examples/<Name>/<Name>.ino`, sem espaços em `<Name>`. Mantenha os dados específicos do exemplo nessa pasta e confirme que o sketch compila com a configuração suportada. Execute `make build-<Name>` antes de enviar a alteração e depois `make build` para verificar o conjunto completo.

## Alterar a documentação

Escreva primeiro o arquivo em inglês em `docs/en/`, adicione a tradução pt-BR com o mesmo nome em `docs/pt-BR/` e atualize o README correspondente se necessário. Execute `make docs` para verificar links e pares de idioma e gerar o HTML do Doxygen.

O workflow do Pages usa Doxygen 1.18.0. Instale a mesma versão localmente para que os avisos gerados coincidam com a CI; o workflow baixa o binário oficial para Linux da versão fixada em `DOXYGEN_VERSION`.
