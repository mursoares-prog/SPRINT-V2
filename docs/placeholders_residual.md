# Placeholders residuais — CONCLUÍDO

Todos os placeholders do `packageLines.json` estão tokenizados (`{{campo=glifo}}`). **0 residuais.**

Histórico da restauração (regressão do commit a595215, que apagou os ~114 tokens):
1. Transferência do arquivo antigo (a595215~1) + codemod → 83 campos.
2. Transferência posicional N:N → +3 campos.
3. Pressão de teste de equipamento → `pressaoProva` (24 linhas).
4. Correção de conteúdo do ABAN 254/240 (linhas trocadas vs planilha).
5. 18 linhas com campos existentes (prof, canhao, motorFundo, crDiam, packerFtDiam,
   aplicadorCamisao, pressaoBopPerfuracao, cimentTopoInteriorColuna).
6. 062 → `pressaoCabecaLimite`; 063 → `outrosMegConc`.
7. **3 campos novos criados** (tipo + AppContext + ProjectDataPanel + token):
   - `cimentTopoRevcim` (TOC do REVCIM — ABAN 247/248)
   - `marteleteModelo` + `marteletePonteiraDiam` (ponteira do martelete FT — ABAN 143)

Total: **75 data sub fields**. `pytest backend/tests` 179/179; `tsc -b` limpo.
