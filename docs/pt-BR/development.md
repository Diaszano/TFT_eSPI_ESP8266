[English](../en/development.md) | Português (Brasil)

# Desenvolvimento

## Alvos do Make

Use Python 3.14.7 para as ferramentas de desenvolvimento. Instale as ferramentas com versões e hashes fixados usando `python -m pip install --require-hashes -r scripts/requirements-dev.txt`; o build usa a plataforma ESP8266 4.2.1 e acompanha entradas aninhadas da biblioteca e dos exemplos para que inclusões, alterações e remoções invalidem builds em cache.

Use clang-format 23.1.2 dos requisitos bloqueados. `make format-check` verifica fontes C++, Arduino e sketches sem editá-los; execute `make format` somente quando quiser formatar esses arquivos. Tabelas de fontes geradas, dados de inicialização ST7789 e a ferramenta de geração de fontes ficam excluídos. A ordem dos includes é preservada. Depois que a alteração dedicada de formatação for integrada, configure o blame com `git config blame.ignoreRevsFile .git-blame-ignore-revs` usando o SHA final do commit integrado.

Execute `make test-native` para os testes puros de conversão de cores. Eles exercitam somente os auxiliares compartilhados de conversão inteira; não simulam o core ESP8266, PROGMEM, temporização do display, uso de heap ou renderização. Use os exemplos PlatformIO e um dispositivo para essas verificações.

Use `make docs-examples` para compilar os primeiros exemplos C++ dos dois READMEs e dos guias de Sprite usando a biblioteca preparada. Use um dispositivo para as verificações do display.

Execute `make warnings` para reconstruir os 14 exemplos em `.build/warnings/` com `-Wall -Wextra`. A linha de base de avisos próprios é revisada manualmente; novos avisos falham, avisos resolvidos são relatados para remoção e os avisos do framework/core ficam em um relatório separado. Não edite a linha de base automaticamente.

`make compiledb` prepara o banco de compilação Xtensa verificado. `make tidy` executa um piloto opcional do parser clang-tidy 22.1.8 para o alvo; as flags atuais do compilador ESP8266 e os cabeçalhos do SDK geram erros de análise, portanto não é uma verificação obrigatória. Consulte a documentação [LLVM 22.1.8](https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-22.1.8/clang-tools-extra/docs/clang-tidy/index.rst) e [LLVM 23.1.2](https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-23.1.2/clang-tools-extra/docs/clang-tidy/index.rst) para as versões do piloto e da documentação solicitada.

`make cppcheck` é um piloto opcional do PlatformIO sobre o código-fonte da biblioteca preparada, incluindo os fragmentos `.inc`. O piloto resolveu o cppcheck 2.11 (`tool-cppcheck` 1.21100.230717) e relatou 24 avisos existentes em `.build/analysis/cppcheck.json`. O comando apenas gera um relatório, não tem linha de base e não é executado na CI.

| Alvo | Finalidade |
| --- | --- |
| `make build` | Compila todos os exemplos selecionados. |
| `make build-<Name>` | Compila um exemplo, como `make build-Colour_Test`. |
| `make upload EX=<Name> PORT=<port>` | Envia um exemplo à placa. |
| `make uploadfs EX=<Name> PORT=<port>` | Envia os dados do sistema de arquivos de um exemplo. |
| `make monitor PORT=<port>` | Abre o monitor serial. |
| `make clean` | Remove os arquivos gerados de build. |
| `make warnings` | Reconstrói os exemplos e verifica avisos próprios do compilador. |
| `make compiledb` | Valida e mapeia o banco de compilação do alvo. |
| `make tidy` | Executa o piloto não obrigatório do parser clang-tidy para Xtensa. |
| `make cppcheck` | Gera o relatório cppcheck opcional do código preparado da biblioteca. |
| `make docs-check` | Verifica pares de documentação, links e referências a APIs removidas. |
| `make docs` | Executa as verificações da documentação e gera a referência da API. |
| `make help` | Lista os alvos disponíveis. |

A CI compila os exemplos selecionados com PlatformIO. O workflow de documentação verifica e gera os arquivos; o job de publicação no Pages executa somente em pushes para `main`.

`make size-check` falha se o uso estático de flash ou RAM aumentar ou se o perfil de build mudar. O total de RAM inclui dados inicializados, dados somente leitura e BSS; ele não mede o heap usado em tempo de execução por sprites, fontes ou outras alocações.

## Estrutura da biblioteca Arduino

Arduino e PlatformIO compilam `src/TFT_eSPI.cpp` como a única unidade de tradução de produção da biblioteca. Sprite, fonte suave, driver e dados das fontes embutidas são fragmentos incluídos; mantenha-os como `.inc` ou headers, nunca como arquivos `.cpp`/`.c` compilados separadamente. O `User_Setup.h` editável permanece na raiz do pacote.

## Adicionar um exemplo

Crie `examples/<Name>/<Name>.ino`, sem espaços em `<Name>`. Mantenha os dados específicos do exemplo nessa pasta e confirme que o sketch compila com a configuração suportada. Execute `make build-<Name>` antes de enviar a alteração e depois `make build` para verificar o conjunto completo.

A CI também executa `make test-native` para conversões puras de cor e `make test-compile` para testar a propriedade do Sprite e uma configuração mínima somente com `LOAD_GLCD`. Essas verificações não substituem os 14 builds de exemplo nem os testes físicos do display.

## Alterar a documentação

Escreva primeiro o arquivo em inglês em `docs/en/`, adicione a tradução pt-BR com o mesmo nome em `docs/pt-BR/` e atualize o README correspondente se necessário. Execute `make docs` para verificar links e pares de idioma e gerar o HTML do Doxygen.

O workflow do Pages usa Doxygen 1.18.0. Instale a mesma versão localmente para que os avisos gerados coincidam com a CI; o workflow baixa o binário oficial para Linux da versão fixada em `DOXYGEN_VERSION`.
