# Validação física ESP8266 + ST7789

Este sketch é uma ferramenta manual para NodeMCU ESP8266 com ST7789 240×240. `User_Setup.h` é a referência para pinos e frequências. O display é write-only nesta configuração; inspeção visual humana continua necessária.

No boot, o firmware inicializa e emite `HWTEST,2`, `RUN` e `READY`; nenhuma suíte inicia automaticamente. Envie comandos como linhas completas a 115200 baud: `?`, `B`, `S`, `S1`–`S4`, `R0`–`R3`, `L`, `M`, `E30` ou `X`. `R0`–`R3` seleciona a orientação e emite `ROTATION,n`; o parser associa essa orientação ao próximo `CASE,START`. Em seguida rode a cena compartilhada selecionada, por exemplo `S1`.

- `B`: 16 cenários, três rodadas por dez amostras; os resultados são medições locais e não substituem cinco boots independentes por revisão.
- `S` / `S1`–`S4`: quatro padrões visuais. Cada retorno permanece `VISUAL_REVIEW_REQUIRED` até revisão humana. S3 mostra sprites assimétricos em 0°/45°/90° e clipping 13×13; S4 separa amostras legíveis, opacidade, transparência e clipping de texto. `N` avança e `Q` encerra. Consulte [TESTES.md](TESTES.md) para posições e revisão esperada.
- `L`: 10.000 ciclos; progresso a cada 1.000 e marcador `STRESS,END` obrigatório.
- `M`: perfis de criação/limpeza de sprites e tentativa de alocação grande.
- `E30`: endurance opcional de 30 minutos; só inicia por comando e `Q` aborta como `INCONCLUSIVE`.
- `X`: casos limitados com buffers válidos; o caso de sprite fica `SKIP` até o caminho host correspondente ser coberto.

Build compile-only: `make test-hw-build`. A saída vai para `.build/hardware/validation-<sha>-<clean|dirty>`. Para gerar o relatório H0 com o SHA-256 do binário, revisão, perfil e próximos limites de autorização, execute `make test-hw-preflight`; os relatórios ficam em `.build/hardware/preflight-<sha>-<clean|dirty>/`. Uma árvore suja é marcada `BLOCKED`. Nenhum alvo offline faz upload, abre serial ou aciona reset. Gravação e testes físicos são passos manuais separados, com autorização explícita e sem DTR/RTS automático.

`test-hw-preflight` é evidência de build, não aprovação para gravar. O relatório deixa porta serial não selecionada, upload não autorizado e testes físicos como `NOT_EXECUTED`. Antes de qualquer ação, o operador deve conferir o checksum, placa/módulo, alimentação, fiação e procedimento manual sem reset automático; o gate H1 exige autorização explícita separada.

Para instruções de execução, comparação, estados e evidências pendentes, consulte [TESTES.md](TESTES.md). Os inventários antigos, o guia herdado e `test_demo.mp4` são proveniência/ilustração; não provam pixels, desempenho ou segurança.
