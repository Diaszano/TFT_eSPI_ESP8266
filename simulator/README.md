# Simulador gráfico ST7789

Este é um **simulador gráfico funcional; não emula CPU ESP8266**. O build nativo executa os caminhos de desenho reais da biblioteca (`TFT_eSPI.cpp` e `TFT_eSprite`); somente a camada de transporte SPI é adaptada para o host. O simulador produz frames RGB565 determinísticos, mas não modela temporização de hardware, consumo de RAM/flash, sinais elétricos, MISO ou as cores ópticas de um painel.

## Construir e testar

Requisitos locais: CMake, compilador C++11, Python 3 e ASan/UBSan suportados pelo compilador.

```sh
make sim-build
make sim-test
make test-host
make test-host-extremes
make test-native
make test-compile
make test-hw-build
make test-hw-preflight
```

O target `test-hw-build` apenas compila o sketch de validação. `test-hw-preflight` acrescenta um relatório local com SHA-256 do binário, source SHA e perfil; árvore suja fica `BLOCKED`. Nenhum dos dois grava firmware, abre serial ou reinicia uma placa. O relatório H0 não autoriza upload. `sim-test` é headless, executa sem hardware e não inicia servidor ou navegador.

## Renderizar, comparar e visualizar

```sh
make sim-render SCENE=edge_rect SEED=123 OUT=.build/simulator/runs/edge_rect
make sim-preview RUN=.build/simulator/runs/edge_rect
```

O preview inicia explicitamente um servidor read-only em `127.0.0.1`; pare com Ctrl+C. Ele serve somente os assets fixos do viewer e artefatos permitidos de diretórios de execução válidos vizinhos ao `RUN`. Não serve arquivos-fonte ou diretórios arbitrários do repositório.

O CLI também pode ser usado diretamente:

```sh
python3 simulator/tools/sim.py list-scenes
python3 simulator/tools/sim.py render --scene edge_rect --seed 123 --out .build/simulator/runs/edge_rect
python3 simulator/tools/sim.py diff --expected baseline/frame.rgb565 --actual .build/simulator/runs/edge_rect/frame.rgb565 --out .build/simulator/runs/edge_rect
```

`frame.rgb565` contém pixels em ordem row-major, RGB565 little-endian. `frame.png` é determinístico e usa pixels RGB sem interpolação. `manifest.json` registra cena, seed, rotação, revisão, perfil e SHA-256 do frame. O viewer permite navegar execuções, usar zoom inteiro 1×/2×/4×/8×, inspecionar coordenadas e RGB565/RGB888, e mostrar o PNG de diferenças sobre a imagem candidata. O status é lido dos resultados/relatórios e nunca é aprovado por abrir ou navegar no viewer.

`make sim-diff EXPECTED=<diretório> ACTUAL=<diretório>` propaga o código de saída do comparador. Uma diferença é `FAIL`; referência ausente ou sem aprovação independente é `NO_BASELINE`; perfil ou integridade incompatível é `INCONCLUSIVE`. `PASS` só é possível com uma referência explicitamente aprovada. Geração de frame não aprova nem sobrescreve golden; aprovação exige revisão independente, motivo registrado e atualização manual versionada.

Status possíveis incluem `PASS`, `FAIL`, `SKIP`, `INCONCLUSIVE`, `VISUAL_REVIEW_REQUIRED`, `UNSUPPORTED` e `NO_BASELINE`. Uma cena exibida com resultado `RENDERED` significa apenas que o caminho de desenho produziu bytes. Estas são as limitações do host, não validações do painel real.

## Cobertura e fidelidade

| Área | Execução no host | Correção independente de pixels |
|---|---|---|
| Preenchimento RGB565 e primitivas | Sim, caminho de produção | Coberta pelos oráculos/casos de Planos 01–02 e cenários Plan 09 |
| Clipping de primitivas e imagens | Sim | Coberto por casos determinísticos, incluindo bordas |
| Sprites 1/4/8/16 bpp | Sim | Comparação com expectativa independente |
| Rotações 0–3 | Sim | Matriz assimétrica e teste de transporte/controlador |
| Texto | Executa | Precisão dos glifos RLE não verificada: golden host independente ausente; `text_edges` é `SKIP` |
| Cenas compartilhadas S1–S4 | Executam | Revisão visual manual pendente: `VISUAL_REVIEW_REQUIRED` |
| Exportação RGB565 e comparação | Sim | Comparação exata por pixel e mutação de um pixel |
| Viewer | Sim, local | Apresentação visual do host; não prova fidelidade óptica |
| Temporização SPI, consumo e comportamento físico | Não simulado | Requer testes físicos separados |
| Cores do painel e validação de tela | Não | Requer aprovação manual no hardware real |

O GitHub Actions executa CMake/CTest com ASan/UBSan, testes Python, integração Makefile, render determinístico e regressão de mutação. O runtime de teste não usa rede, GUI, browser, USB ou hardware; Actions pode baixar as próprias actions durante bootstrap. Falhas retêm somente frames/manifestos/relatórios do diretório de build com retenção limitada.

As referências aprovadas, metadados e política de baseline estão em [`tests/goldens/README.md`](tests/goldens/README.md). Para detalhes do backend host e limitações, veja [`native/FEASIBILITY.md`](native/FEASIBILITY.md). A implementação não suporta leitura MISO/touch no host e não substitui teste físico de SPI, cores, temporização ou consumo.
