English | [Português (Brasil)](CONTRIBUTING.pt-BR.md)

# Contributing

## Setup and checks

Run `make setup` once, then run `make build lint docs` before opening a pull request.

## Branches and commits

Use conventional branch names and [Conventional Commits](https://www.conventionalcommits.org/). Pull request titles must use a Conventional Commit format because squash merges use that title as the commit message.

## Documentation

Write English documentation first, then update its Brazilian Portuguese pair. See the [documentation guide](docs/en/development.md).

## Git blame

Configure Git to ignore the formatting commit with `git config blame.ignoreRevsFile .git-blame-ignore-revs`.

## Updating an old clone after the default branch changes

Run:

```sh
git branch -m master main && git fetch origin && git branch -u origin/main main && git remote set-head origin -a
```
