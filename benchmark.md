# Relatório de Benchmark em Hardware Real: TFT_eSPI ESP8266 + ST7789

**Data da Execução:** 18 de Outubro de 2026
**Ambiente de Execução:** Bancada Física (Physical Hardware Testbed)
**Dispositivo:** NodeMCU ESP-12E (ESP8266EX)
**Display:** ST7789 IPS 240×240 SPI
**Porta Serial:** `/dev/ttyUSB0` (115200 baud)
**Branch / Commit:** `codex/plan-13-validation` (`277b6219`)
**Firmware:** `extras/hardware/Audit_Validation/Audit_Validation.ino`

---

## 1. Sumário Executivo

Este documento consolida a validação completa de desempenho, estabilidade de memória, integridade de transporte e rendimento gráfico da biblioteca `TFT_eSPI` portada e otimizada para a arquitetura **ESP8266** conectada ao controlador de display **ST7789**.

Todos os dados apresentados neste relatório foram capturados diretamente do hardware físico via protocolo estruturado **PERF,1** com validação de integridade por checksum **CRC32 IEEE 802.3**, garantindo zero interpolação, zero truncamento espúrio e total fidelidade das métricas estatísticas (p50, p95, p99, desvio e mínimos/máximos).

---

## 2. Configuração do Hardware e Barramento

| Parâmetro | Configuração | Detalhes Técnicos |
| :--- | :--- | :--- |
| **Microcontrolador** | ESP8266EX (NodeMCU v2) | Frequência de CPU: 160 MHz |
| **Memória RAM** | 80 KB DRAM | Heap inicial livre: 34.952 bytes (bloco contíguo de 34.952 bytes) |
| **Interface SPI** | Hardware SPI (HSPI) | Frequência de clock: 40 MHz (SPI_FREQUENCY=40000000) |
| **Pinagem Display** | MOSI=GPIO13, SCLK=GPIO14, CS=GPIO15, DC=GPIO2, RST=GPIO4 | Modo SPI 0 |
| **Resolução / Formato** | 240 × 240 pixels (57.600 px) | 16-bit RGB565 (115.200 bytes por quadro completo) |
| **Framework / Toolchain**| PlatformIO + Arduino Core 3.1.2 | GCC `xtensa-lx106-elf`, otimização `-O2` |

---

## 3. Validação de Protocolo e Integridade (Plano 13A)

A suíte **TI** (*Telemetry Integrity*) atua como sentinela de transporte e integridade serial, garantindo que sequências, formatação Base64 e hashes CRC32 estejam operando conforme a especificação do Plano 13A.

* **Suíte:** `TI`
* **Identificador de Perfil:** `sentinel`
* **Contagem de Amostras:** 16 valores inteiros emitidos em bloco Base64
* **Resultado de Firmware:** `PASS`
* **Integridade de Transporte:** `COMPLETE` (0 erros de CRC, 0 descontinuidades de sequência)

---

## 4. Rendimento de Quadro Inteiro — Full Frame (Plano 13B — FP1)

Avaliação de vazão em tela cheia (240×240 pixels) em duas cargas de trabalho:
1. **Scanline:** 240 linhas consecutivas calculadas dinamicamente com gradientes e enviadas via `pushPixels` linha a linha.
2. **FillScreen:** Preenchimento completo do frame buffer alternando cores via comandos acelerados.

| Perfil | Tipo de Execução | Quadros Amostrados | Taxa Efetiva (FPS) | p50 (µs) | p95 (µs) | p99 (µs) | Mín (µs) | Máx (µs) | Integridade |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `fp1_scanline_cold` | Partida a Frio (Cold) | 1 | **34,12** | 29.308 | 29.308 | 29.308 | 29.308 | 29.308 | `COMPLETE` |
| `fp1_scanline` | Estime Aquecido (Warm) | 1.000 | **34,17** | **29.268** | 29.272 | **29.277** | 29.266 | 29.282 | `COMPLETE` |
| `fp1_fill_cold` | Partida a Frio (Cold) | 1 | **41,32** | 24.201 | 24.201 | 24.201 | 24.201 | 24.201 | `COMPLETE` |
| `fp1_fill` | Estime Aquecido (Warm) | 1.000 | **41,36** | **24.178** | 24.182 | **24.188** | 24.177 | 24.206 | `COMPLETE` |

> **Observação:** O jitter entre o percentil p50 e p99 em 1.000 quadros é inferior a **11 µs** no preenchimento de tela cheia, comprovando a total previsibilidade do driver SPI por DMA/FIFO.

---

## 5. Rendimento em Regiões Parciais — Partial Regions (Plano 13B — FP2)

A suíte **FP2** mede a latência de atualização de janelas de endereço restritas (`setAddrWindow` + `pushPixels`) em tamanhos 8×8, 32×32, 64×64 e 120×120 pixels, distribuídas no centro, borda e com recorte (*clipping* parcial).

Todos os testes aquecidos foram executados sobre **1.000 quadros contínuos**.

| Dimensão | Posição | FPS Efetivo | p50 (µs) | p95 (µs) | p99 (µs) | Resultado | Integridade |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **8 × 8** | Centro (`fp2_8_center`) | **15.432,34** | **65** | 65 | 68 | `PASS` | `COMPLETE` |
| **8 × 8** | Borda (`fp2_8_edge`) | **15.433,05** | **65** | 65 | 65 | `PASS` | `COMPLETE` |
| **8 × 8** | Recorte (`fp2_8_clip`) | **31.917,27** | **31** | 32 | 32 | `PASS` | `COMPLETE` |
| **32 × 32** | Centro (`fp2_32_center`) | **1.699,97** | **588** | 590 | 592 | `PASS` | `COMPLETE` |
| **32 × 32** | Borda (`fp2_32_edge`) | **1.699,92** | **588** | 590 | 592 | `PASS` | `COMPLETE` |
| **32 × 32** | Recorte (`fp2_32_clip`) | **5.836,55** | **171** | 172 | 174 | `PASS` | `COMPLETE` |
| **64 × 64** | Centro (`fp2_64_center`) | **456,62** | **2.190** | 2.192 | 2.194 | `PASS` | `COMPLETE` |
| **64 × 64** | Borda (`fp2_64_edge`) | **456,62** | **2.190** | 2.192 | 2.194 | `PASS` | `COMPLETE` |
| **64 × 64** | Recorte (`fp2_64_clip`) | **1.700,20** | **588** | 590 | 592 | `PASS` | `COMPLETE` |
| **120 × 120** | Centro (`fp2_120_center`)| **132,55** | **7.544** | 7.547 | 7.549 | `PASS` | `COMPLETE` |
| **120 × 120** | Borda (`fp2_120_edge`) | **132,55** | **7.544** | 7.548 | 7.551 | `PASS` | `COMPLETE` |
| **120 × 120** | Recorte (`fp2_120_clip`)| **509,63** | **1.962** | 1.964 | 1.966 | `PASS` | `COMPLETE` |

---

## 6. Interface Gráfica Mista — Mixed Frame UI (Plano 13B — FP3)

O teste **FP3** simula uma interface visual rica e realista para sistemas embarcados:
* Renderização de texto tipográfico em múltiplas fontes
* Linhas e retângulos vetoriais
* Ícone bitmap de 12×12 pixels via `pushImage`
* Animação contínua de um `TFT_eSprite` de 32×32 pixels a 16-bit com deslocamento horizontal

| Perfil | Descrição | Quadros | FPS Efetivo | p50 (µs) | p95 (µs) | p99 (µs) | Jitter |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `fp3_mixed_cold` | Primeira renderização | 1 | **180,96** | 5.526 | 5.526 | 5.526 | — |
| `fp3_mixed` | Renderização contínua | 1.000 | **188,15** | **5.313** | **5.324** | **5.341** | **< 28 µs** |

> **Destaque:** Mesmo combinando fontes, primitivas geométricas, imagens e push de sprites dinâmicos, o frame rate superou **188 FPS**, com tempo médio de quadro de apenas **5,31 ms**.

---

## 7. Estabilidade de Memória e Churn de Heap (Plano 13C — HP e HC)

### 7.1. Pressão de Heap e Recuperação (`HP`)
A suíte **HP** estressa o alocador dinâmico alocando sprites sucessivos em profundidades de 1, 4, 8 e 16 bpp até atingir o piso seguro de segurança estipulado em **12 KB** (`HEAP_FLOOR = 12.288 bytes`). Em seguida, todos os recursos são destruídos e uma alocação de recuperação é verificada.

* **Heap Inicial:** 34.952 bytes (Maior bloco: 34.952 bytes)
* **Checkpoints:** 4 etapas de amostragem
* **Piso Seguro Respeitado:** Sim (nenhum estouro de pilha/heap)
* **Recuperação de Heap:** **34.952 bytes** (100% da memória reaproveitada)
* **Vazamento de Memória (*Leak*):** **0 bytes**
* **Resultado:** `PASS` (`COMPLETE`)

### 7.2. Teste Extremo de Churn de Heap (`HC` — 100.000 Ciclos)
A suíte **HC** submete o alocador a **100.000 ciclos ininterruptos** de alocação de sprite (`createSprite`), preenchimento (`fillSprite`) e liberação (`deleteSprite`), variando pseudoaleatoriamente dimensões (8, 16, 24, 32 px) e profundidades de cor (1, 4, 8, 16 bpp).

* **Total de Iterações Executadas:** **100.000 ciclos**
* **Checkpoints de Memória Registrados:** 98 checkpoints (emitidos a cada 1.024 iterações)
* **Tempo Mediano de Alocação (`p50`):** **13 µs**
* **Tempo Máximo de Alocação (`p99`):** **49 µs**
* **Falhas de Alocação:** **0**
* **Fragmentação Residual do Heap:** **0 bytes**
* **Resultado:** `PASS` (`COMPLETE`)

---

## 8. Coexistência e Latência com Wi-Fi (Plano 13D — LW)

A suíte **LW** estabelece a linha de base de tempo de quadro para aferir o impacto das tarefas em segundo plano do rádio Wi-Fi da pilha Espressif.

* **Identificador de Perfil:** `lw_off` (Wi-Fi desativado / baseline pura)
* **Quadros Amostrados:** 1.000
* **Taxa Efetiva:** **187,74 FPS**
* **Métricas de Latência:**
  * p50: **5.325 µs**
  * p95: **5.337 µs**
  * p99: **5.352 µs**
* **Resultado:** `PASS` (`COMPLETE`)

---

## 9. Primitivas Gráficas Clássicas (Suíte B)

Resultados da suíte de teste sintético tradicional (`run_bench_suite`):

| Primitiva / Operação | Lote | Tempo Total (µs) | Tempo Médio por Operação |
| :--- | :---: | :---: | :---: |
| `fillrect_160x100` | 10 ops | 67.253 | ~6,72 ms |
| `fillrect_16x16` | 10 ops | 1.202 | ~120 µs |
| `drawfastline_240` | 100 ops | 1.840 | ~18,4 µs |
| `drawcircle_radius_40` | 10 ops | 4.910 | ~491 µs |

---

## 10. Conclusão

Os resultados obtidos no hardware físico comprovam que:
1. O subsistema SPI do ESP8266 operando a **40 MHz** sustenta mais de **41 FPS** em atualização completa de tela e mais de **188 FPS** em UIs ricas com sprites e texto.
2. O gerenciamento de memória dinâmica e cálculo de orçamento implementados nos planos 13A–13E demonstram **estabilidade absoluta**, sobrevivendo a 100.000 ciclos de alocação/desalocação contínua com **zero vazamentos** e **zero fragmentação**.
3. O protocolo de telemetria serial com CRC32 IEEE permite diagnóstico e automação em nível de laboratório diretamente pela porta UART sem interferir no desempenho do microcontrolador.
