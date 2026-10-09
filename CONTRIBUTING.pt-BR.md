[English](CONTRIBUTING.md) | Português (Brasil)

# Como contribuir

## Configuração e verificações

Use Python 3.14.7 e instale as ferramentas com hashes fixados usando `python -m pip install --require-hashes -r scripts/requirements-dev.txt`. Execute `make setup` uma vez e, antes de abrir um pull request, rode `make build lint docs`.

## Branches e commits

Use nomes de branches convencionais e [Conventional Commits](https://www.conventionalcommits.org/). O título do pull request deve seguir esse formato, pois o squash usa o título como mensagem do commit.

## Documentação

Escreva primeiro em inglês e depois atualize o par em português brasileiro. Consulte o [guia de desenvolvimento](docs/pt-BR/development.md).

## Git blame

Configure o Git para ignorar o commit de formatação com `git config blame.ignoreRevsFile .git-blame-ignore-revs`.

## Atualizar um clone após a mudança da branch padrão

Execute:

```sh
git branch -m master main && git fetch origin && git branch -u origin/main main && git remote set-head origin -a
```
