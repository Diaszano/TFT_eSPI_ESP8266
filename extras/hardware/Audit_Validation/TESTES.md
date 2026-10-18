# Guia de validação ESP8266 + ST7789

Este firmware é uma ferramenta manual. No boot ele só inicializa o display, emite `HWTEST,2`, `RUN` e `READY`, e mostra o menu. Nenhuma suíte roda automaticamente. O display ST7789 é write-only nesta configuração: `CASE,RETURN` e `VISUAL_REVIEW_REQUIRED` não confirmam os pixels; uma pessoa precisa inspecionar a tela.

## Preparação segura

1. Compile sem gravar e crie a evidência H0: `make test-hw-preflight`. Confira `preflight.md`/`preflight.json` em `.build/hardware/preflight-<sha>-<clean|dirty>/`, o caminho do firmware e seu SHA-256. Uma árvore dirty fica `BLOCKED`; não use um build de outra revisão.
2. Confirme placa NodeMCU ESP8266, ST7789 240×240, pinos e frequências em `User_Setup.h`, alimentação e cabo USB estáveis.
3. **H1: pare antes de abrir serial ou gravar.** Obtenha autorização explícita para o checksum exato, placa/painel e procedimento escolhido pelo operador. A porta é selecionada manualmente; não habilite reset automático: sem DTR/RTS. Confirme manualmente antes de entrar no bootloader. Depois do upload, o operador deve confirmar o reboot; somente então peça autorização separada para observar serial. O pedido do Plano 12 não é autorização para essas ações.
4. Após as autorizações H2, aguarde `READY`, salve o log completo e verifique SHA, placa, driver, dimensões, rotação, CPU, SPI, Wi-Fi e flags do `RUN`. Se algum campo necessário estiver `unknown`, a execução não serve para comparação. Sem essa evidência, mantenha o status físico `NOT_EXECUTED`/`BLOCKED`.

## Execução manual

Faça uma suíte por vez e salve o log bruto de cada boot.

### Matriz física do Plano 12

Antes de cada grupo, obtenha autorização H3 separada. Use `R0`, `R1`, `R2` ou `R3` antes de `S1`–`S4`; confirme `ROTATION,n` no log. Para comparação host use a mesma cena compartilhada (`s1`–`s4`), revisão, perfil, rotação e seed 0. Uma foto registra apenas revisão visual, nunca pixels RGB565 lidos do GRAM.

| Grupo | Cobertura | Evidência física requerida | Estado sem execução autorizada |
| --- | --- | --- | --- |
| A — Inicialização | Energia, backlight, init, cores primárias, idle | Observação do operador, log `HWTEST,2`/`RUN`/`READY`, perfil confirmado | `BLOCKED` |
| B — Rotação/endereço | `R0`–`R3`, quatro cantos assimétricos, bordas e offsets | Um `ROTATION,n` por caso, S1, observação manual de orientação/cantos | `VISUAL_REVIEW_REQUIRED` |
| C — Primitivas | Pixel/linhas/retângulos/círculos, clipping, negativo, parcial e vazio | S1 e casos X aprovados separadamente; foto/observações por ID | `BLOCKED` |
| D — Imagens/sprites | RGB565/crop, transparência, 1/4/8/16 bpp e paletas quando compilados | S2/S3 e M; marcar capacidades ausentes `SKIP`; nunca inferir suporte | `BLOCKED` |
| E — Texto/fontes | Alinhamento, opaco/transparente, borda, espaçamento e RLE | S4 e observação humana; sem golden RLE independente, comparação exata `SKIP`/`INCONCLUSIVE` | `VISUAL_REVIEW_REQUIRED` |
| F — S1–S4 | Funções `ValidationVisualScenes.cpp` compartilhadas entre firmware/host | Mesmos IDs, rotação, profile e seed; fotos opcionais mais aprovação assinada | `VISUAL_REVIEW_REQUIRED` |
| G — Desempenho | `B`: fill, primitivas, imagens, sprites, texto e clipping disponível | Medições reais, SPI/CPU fixos, cinco boots por revisão, mediana/p95 | `BLOCKED` |
| H — Memória/estabilidade | `M`, `L`, heap/bloco maior, resets/watchdog; E30 separado | Log completo, checkpoints/end marker e análise do operador | `BLOCKED` |
| I — Extremos | `X` allowlist limitada, buffers válidos | Aprovação própria, IDs limitados e log completo; não repetir após reset | `BLOCKED` |

Host snapshots/diffs e o viewer são evidência digital do simulador. Não medem timing ou heap do ESP8266, nem validam cor física/óptica. Sem MISO, uma câmera comum não fornece comparação RGB565 exata.

1. **`B` primeiro:** mede 16 cenários, em três rodadas de dez amostras. O intervalo cronometrado não inclui preparação, escrita serial nem alocação. Guarde todas as linhas `BENCH`; não trate fixtures sintéticas como medições.
2. **`S` ou `S1`–`S4`:** mostra clipping, imagem, sprite e texto. `S` avança por quatro telas; envie `N` para a próxima ou `Q` para sair. O retorno fica `VISUAL_REVIEW_REQUIRED`; registre fotos e revisão humana. S3 e S4 agora exportam frames host para inspeção, mas o status continua exigindo revisão física. A fonte 4 não tem golden RLE independente.
3. **`L`:** roda 10.000 ciclos, publica checkpoints de 1.000 e chama `yield()` pelo menos a cada 16 ciclos. Exija `STRESS,END,L,10000,...`; interrupção ou ausência do marcador final é `INCONCLUSIVE`.
4. **`X` por último:** executa apenas coordenadas limitadas e buffers válidos. O caso de sprite aparece como `SKIP` até haver teste host do caminho de envio. Não envie coordenadas arbitrárias nem repita automaticamente após reset.
5. **`M` é separado:** cria e libera sprites de várias profundidades e tenta uma alocação grande; falha dessa alocação é tratada com segurança, não como falha obrigatória.
6. **`E30` é separado e opcional:** só inicia ao receber o comando explícito. Dura 30 minutos; `Q` aborta com `INCONCLUSIVE`. Reboot não retoma o ensaio.

Para perfis comparáveis, recolha **5 boots independentes** na revisão base e 5 na candidata, todos com o mesmo hardware/configuração e SHA consistente em cada revisão. A comparação ignora SHA ao comparar o perfil, mas exige que cada conjunto tenha um SHA único conhecido. Não use rede Wi-Fi, alimentação ou cabos diferentes sem tratar isso como outro perfil. Uma queda pós-limpeza acima de 1.024 bytes é um aviso para investigar, não prova isolada de leak.

## Análise offline

```sh
make test-hw-parse LOG=capturas/run.log
python3 scripts/hw_validation_compare.py --candidate capturas/base --output-dir .build/hardware/results
make test-hw-compare BASELINE=baseline-aprovada.json CANDIDATE=capturas/candidata
make test-host-extremes
```

`test-hw-compare` requer baseline e candidato. Sem baseline, o relatório informa `NO_BASELINE` e não calcula deltas. A comparação exige cinco boots por revisão, amostras completas, IDs distintos e perfil compatível. `REGRESSION_CANDIDATE` pede revisão humana; não é uma falha automática de release. Relatórios JSON/Markdown não copiam as linhas serial brutas e removem Wi-Fi/flags fora da lista segura.

## Matriz AC-01–AC-14

| Critério | Evidência offline atual | Estado físico / limite |
| --- | --- | --- |
| AC-01 | Dispatcher compilado; boot sem suíte automática | Boot real pendente |
| AC-02 | Estatística e comparação cobertas por fixtures sintéticas | Sem medições físicas; pendente |
| AC-03 | Teste de fonte confirma 3×10 e ausência de I/O/alocação cronometrados | Cobertura de hardware pendente |
| AC-04 | Oráculo, clipping, imagem, sprite pixel e fonte 2 sob ASan/UBSan | Fontes 1/4 e caminho `pushSprite` host incompletos |
| AC-05 | Parser preserva `VISUAL_REVIEW_REQUIRED` | Inspeção humana pendente |
| AC-06 | L, checkpoints, heap e parser implementados/testados | Execução física pendente |
| AC-07 | E30 explícito, cancelável e testado por código | Não executado; pendente |
| AC-08 | Casos INT32 isolados, timeout de 2 s e fuzz com corpus | Sem garantia para APIs fora dos casos cobertos |
| AC-09 | X limitado; sprite excluído com `SKIP` | Execução física pendente |
| AC-10 | Fixtures de status, reset, truncamento, visual e duplicatas | Offline verificado |
| AC-11 | Perfis incompatíveis e baseline ausente não geram delta | Offline verificado |
| AC-12 | Make e workflows contêm apenas compilação/testes no caminho offline | Auditoria final pendente |
| AC-13 | Correção isolada de overflow em viewport com regressão | Suítes finais pendentes |
| AC-14 | Este roteiro descreve comandos, limites e evidência necessária | Uso físico ainda pendente |

Nenhum vídeo ilustrativo conta como evidência física. O CI não executa upload, endurance, B/S/L/X físico ou validação visual. Os resultados manuais abaixo são evidência apenas da revisão gravada identificada em cada seção; a captura serial incompleta de E30 está identificada separadamente do status terminal reportado pelo firmware.

## Diagnóstico de boot e serial

O `RUN` registra agora o motivo de reset retornado por `ESP.getResetReason()`; `unknown` literal no firmware anterior não permitia investigar reinicializações. Capture o boot completo antes de enviar qualquer comando. O ROM do ESP8266 usa 74880 baud e o firmware usa 115200 baud, então bytes de boot ilegíveis a 115200, isoladamente, não indicam corrupção do firmware. Um comando `R0` deve produzir uma única linha `ROTATION,0`; linhas repetidas exigem verificar resets, entrada UART e software do terminal antes de executar `B`, `L`, `M`, `E30` ou `X`. O perfil atual usa GPIO0 para DC e GPIO2 para RST; ambos participam da seleção de boot do ESP8266, portanto confira seus níveis durante a partida sem alterar a pinagem como parte deste diagnóstico.

### Observação física de 2026-10-17

O firmware da revisão `1ed79e3e` (SHA-256 `9b6508751cf1b30bc14356077a4bf08f63b03c805e6fddcf509497fd3790a892`) foi gravado no NodeMCU ESP8266; o esptool informou `Hash of data verified`. Os logs locais estão em `.build/hardware/upload-1ed79e3e/`. Após o upload, cada comando `S1`–`S4` retornou `CASE,RETURN,...,VISUAL_REVIEW_REQUIRED`. O operador comparou a tela com `validation-guide.mp4` e relatou:

| Cena | Observação comunicada pelo operador | Estado da revisão visual |
| --- | --- | --- |
| S1 | Aparência igual ao vídeo; ciano, linha vermelha e linha azul corretos | Aprovada pelo operador |
| S2 | Padrões vermelho/verde corretos, sem azul no lugar do vermelho | Aprovada pelo operador |
| S3 | Quadrantes vermelho/verde/azul/amarelo e marcador ciano corretos nas três rotações | Aprovada pelo operador |
| S4 | Faixas vermelha/azul, texto amarelo e transparência como no vídeo | Aprovada pelo operador |

Essa é uma inspeção visual relatada no chat, sem foto ou leitura do GRAM; não constitui golden RGB565 exato. A captura serial começou depois do reboot e não contém o `RUN` inicial nem o motivo de reset. A origem do fluxo binário visto na primeira abertura da porta permanece inconclusiva. As suítes `B`, `L`, `M`, `E30` e `X` não foram executadas nessa sessão; a referência RLE independente da fonte 4 continua pendente.

### Suítes físicas e build final de 2026-10-17/18

Após a captura serial com RESET manual, `HWTEST,2`, `RUN` e `READY` foram observados na revisão gravada `1ed79e3e`. Na mesma revisão foram executados: `B` com 480 amostras (16 cenários × 3 rodadas × 10 amostras), todos os cenários `OK`; `M` `PASS`, heap e maior bloco estáveis em 35.856 bytes; `L` `PASS`, 10.000 ciclos em 9.942 ms com heap estável; e `X` com cinco casos `PASS` e o caso de sprite `SKIP`. Logs brutos: `.build/hardware/upload-1ed79e3e/bench-physical.bin`, `memory-physical.bin`, `stress-l-physical.bin` e `extremes-x-physical.bin`.

`E30` na revisão `1ed79e3e` foi iniciado, mas o monitor serial parou após o checkpoint 230, em 229.068 ms, sem `STRESS,END` ou `CASE,RETURN`; aquela tentativa permanece `INCONCLUSIVE` em `.build/hardware/upload-1ed79e3e/endurance-e30-physical.bin`.

A revisão final `96abdbda` foi compilada limpa por `make test-hw-build`; o firmware tem 362.528 bytes e SHA-256 `1fcbe9af16e9a4804262c2ef88d270793657933daf12ece661230bad7e9362f6`. Ela acrescenta apenas a guarda que retorna `SKIP` para E30 quando o sprite não foi criado. A primeira tentativa de gravação por esta sessão falhou antes de escrever a flash (`Timed out waiting for packet header`) porque a placa não estava em modo bootloader; depois, o operador informou que instalou a imagem final, e a execução abaixo confirmou o firmware de validação em funcionamento. Não foi usado reset automático nem alterados pinos/frequências.

Em 2026-10-18, `E30` na revisão final encerrou com `STRESS,END,E30,1800,1800554,35856,35856,0,PASS` e `CASE,RETURN,endurance_30m,1800554000,35856,35856,PASS`: 1.800 ciclos em 1.800.554 ms, heap inicial/final e maior bloco em 35.856 bytes, fragmentação 0. A captura local é `.build/hardware/upload-96abdbda/e30-final-physical.bin`. Os dois marcadores finais estão íntegros, portanto o firmware reportou `PASS`; porém, a captura não satisfaz o requisito de transcript serial estável: o primeiro marcador `CASE,START` não foi capturado, 260 checkpoints de progresso estão ausentes e há 408 bytes não ASCII. Considere endurance concluído pelo resultado terminal do firmware, com integridade do transcript incompleta; não use esta captura para análise de boot ou continuidade serial. A leitura read-only da flash via `esptool.py read_flash` recuperou 362.528 bytes sem reset automático; o SHA-256 lido (`1fcbe9af16e9a4804262c2ef88d270793657933daf12ece661230bad7e9362f6`) confere byte a byte com o binário final. Uma repetição do mesmo firmware foi executada em 2026-10-18 após o operador colocar a placa em bootloader e o reset autorizado via esptool. A captura `.build/hardware/upload-96abdbda/e30-final-stable-2.bin` registrou `CASE,START` e os marcadores `STRESS,END,E30,1800,1800549,35856,35856,0,PASS` e `CASE,RETURN,endurance_30m,1800549000,35856,35856,PASS`. Foram 1.780 linhas de progresso até o ciclo 1.800, com 20 checkpoints ausentes, 5 linhas malformadas durante E30 e 63 bytes não ASCII após o início; a captura total contém 120 bytes não ASCII e 6 linhas malformadas. O resultado terminal do firmware é `PASS`, mas a continuidade do transcript serial permanece incompleta.

## Saída esperada de S3 e S4

S3 (`sprite_crop_and_rotation`) mostra três cópias do mesmo sprite assimétrico 64×64 centradas em `(35,71)`, `(120,71)` e `(205,71)`, rotacionadas em 0°, 45° e 90°. O sprite usa quadrantes vermelho/verde/azul/amarelo, borda branca, seta para cima e pivô ciano. Uma alocação temporária de 8.194 bytes (inclui o pixel sentinela de 16 bpp, fora o overhead do allocator) é liberada antes de criar o sprite checker 13×13. Esse checker é enviado em `(-3,146)`: somente as colunas de origem 3–12 devem aparecer na margem esquerda. Se qualquer alocação ou envio rotacionado falhar, `CASE,RETURN` deve ser `FAIL`; não aceite a cena como revisão visual concluída.

S4 (`text_opaque_transparent_edges`) mostra fonte 1 opaca azul, fonte 2 amarela transparente sobre faixas vermelha/azul, fonte 4 opaca azul, uma linha de referência cinza em y=122, texto cortado à esquerda e à direita, e texto cortado na borda inferior. O rodapé `Review pixels; N next, Q stop` fica reservado. As fontes 1/2/4 estão presentes no perfil atual; a renderização RLE da fonte 4 ainda não possui referência independente de glifos e requer revisão visual.

Gere os frames e as imagens de referência anotadas de `S1`–`S4` usando as funções compartilhadas pelo firmware e simulador:

```sh
python3 simulator/tools/sim.py render --scene s3 --seed 0 --out .build/simulator/renders/s3
python3 simulator/tools/sim.py render --scene s4 --seed 0 --out .build/simulator/renders/s4
python3 simulator/tools/sim.py render-references --out .build/simulator/renders
```

Inspecione as imagens `.build/simulator/renders/s1/frame.png` a `.build/simulator/renders/s4/frame.png` (e seus pares `annotated.png`); são referências geradas pelo simulador no host, não baselines aprovados nem evidência de aprovação física.

O resultado `RENDERED` confirma que os caminhos de produção geraram um frame; `review_status: VISUAL_REVIEW_REQUIRED` continua no `result.json` e no manifesto. Não há baseline aprovado para S3/S4. No hardware, inspecione os quatro quadrantes, seta e pivô das três orientações, o recorte de 13×13, as áreas de fundo preservadas e as três bordas de texto. Uma foto é evidência visual, não leitura RGB565 do GRAM.

## Guia em vídeo (`validation-guide.mp4`) para S1–S4

Para gerar e verificar o guia visual reproduzível em MP4 a partir dos artefatos validados de `S1`–`S4`:

```sh
make sim-visual-video
# ou diretamente:
python3 simulator/tools/generate_visual_guide.py --out .build/simulator/renders
```

### Artefatos gerados

- **Vídeo MP4:** `.build/simulator/renders/validation-guide.mp4` (`1920×1080`, H.264 `libx264`, `30` FPS constante, `yuv420p`, CRF 18, `+faststart`, `53,0` s / `1590` quadros, sem áudio e sem marcas d'água).
- **Manifesto e relatório de verificação:** `.build/simulator/renders/video_manifest.json` e `.build/simulator/renders/VIDEO_GUIDE_REPORT.md`.
- **Slides pré-codificação e quadros extraídos:** `.build/simulator/renders/video_slides/slide_00_intro.png`..`slide_05_conclusion.png` e `.build/simulator/renders/video_frames/frame_00_intro.png`..`frame_05_conclusion.png`.

### Como usar o vídeo ao lado do display físico ST7789

1. Abra `.build/simulator/renders/validation-guide.mp4` no computador host ao lado da bancada com o NodeMCU ESP8266 + ST7789 240×240 (após concluir os portões manuais H0–H3).
2. Configure o monitor serial em `115200 8N1` com terminador de nova linha (`\n` ou `\r\n`) e sem reset automático (`sem DTR/RTS`).
3. Acione cada cena no hardware enviando os comandos seriais terminados por newline:
   - `S1\n` — exibe `S1` (`edge_clipping`, trecho `00:04–00:13` do vídeo).
   - `S2\n` — exibe `S2` (`image_source_clipping`, trecho `00:13–00:22` do vídeo).
   - `S3\n` — exibe `S3` (`sprite_crop_and_rotation`, trecho `00:22–00:35` do vídeo).
   - `S4\n` — exibe `S4` (`text_opaque_transparent_edges`, trecho `00:35–00:48` do vídeo).
   - Alternativamente, envie `S\n` para iniciar a sequência interativa `S1`→`S4`, usando `N\n` para avançar à próxima cena e `Q\n` para encerrar a revisão.
4. Pause o vídeo em cada cena e compare o painel físico 240×240 com o framebuffer simulado ampliado em `4×` nearest-neighbor (`960×960`, sem corte nem sobreposição) à esquerda e os critérios objetivos de inspeção + recortes de detalhe `8×` (`256×256`) no painel de informações à direita.
5. No encerramento (`00:48–00:53`), registre `PASS`, `FAIL` ou `INCONCLUSIVE` para cada cena (`S1`–`S4`) junto com a assinatura da revisão visual humana.

### O que o vídeo comprova e o que não comprova

- **O que comprova:** documenta de forma determinística no host a aparência esperada das cenas `S1`–`S4` renderizadas pelo código de produção no simulador, facilitando a inspeção humana lado a lado com o ST7789 físico.
- **O que NÃO comprova:** o vídeo é gerado pelo simulador (`Simulator-generated reference — not physical hardware footage`), **não** é filmagem do hardware físico, **não** substitui a inspeção visual humana no painel ST7789 (`Physical visual review is required`) e **não** valida fiação SPI, temporização do ESP8266, backlight, óptica do display nem consumo de heap. Além disso, por usar compressão H.264 (`yuv420p`) com perdas, o arquivo MP4 é apenas um artefato de apresentação e **nunca** deve ser usado como referência golden exata de pixels (para verificação exata de pixels, use `frame.rgb565` e `frame.png`).
# PERF offline capture and analysis

New suites are opt-in. Sending TI emits a 16-value protocol sentinel; it is
never a hardware speed measurement. During a running suite, Q stops the suite
at a cooperative checkpoint, N advances only visual review, and other
complete commands receive BUSY.

FP1 records separate scanline RGB565 transfers (57,600 pixels and 115,200
payload bytes per warm frame) and the optimized fillScreen path. FP2 records
8, 32, 64, and 120 square-pixel regions at center and bottom-right edge,
plus explicitly clipped half-width/half-height cases. Each scene has a
separate cold frame and 1,000 warm frames. Preparation of scanline pixels
is outside the timed interval; address-window setup and all display writes
are inside it. The reported elapsed window sums measured frame intervals,
excluding serial output and cooperative control checks. Q is checked after
each batch of at most 128 frames.

FP3 draws two text regions, three primitives, a fixed 12×12 cropped RGB565
image, background repair, and a moving 32×32 sprite with seed 324508639.
The sprite and image buffer are prepared before timing. A missing sprite
produces SKIP; it is not a successful frame run. The sketch restores Font 1
and the default non-swapped pixel order after the mixed scene.

The operator must complete hardware gates H1–H3 in the performance validation
spec before any upload or real capture. One operator-owned process opens the
chosen serial port and pipes its raw bytes to the passive capture command.
This repository's offline commands do not open a port, reset a board, upload
firmware, or change DTR/RTS. Record the approved firmware checksum, board,
display, CPU/SPI clocks, Wi-Fi state, boot witness, source SHA, and operator
authorization in a JSON metadata file. Use a new run directory each time.

A synthetic replay that needs no hardware:

~~~sh
printf 'HWTEST,2\n' | python3 -m scripts.hw_perf_capture .build/hardware/perf/example/synthetic --max-bytes 100000 --max-seconds 10
python3 -m scripts.hw_perf_analysis .build/hardware/perf/example/synthetic
make test-hw-perf-offline
~~~

The capture keeps exact bytes in serial.raw; capture.json records its hash,
size and truncation reason. The analysis writes parsed.json,
measurements.csv, summary.json, and report.md without replacing prior
artifacts. Missing operator attestation remains synthetic. A firmware PASS
with a sequence gap remains incomplete transport evidence.
