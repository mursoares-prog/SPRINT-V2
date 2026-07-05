# /review — Revisão de código antes do commit

Revise as mudanças pendentes no working tree antes de commitar.

## Processo

1. Rode `git diff` e `git diff --cached` para ver todas as mudanças
2. Rode `git status` para ver arquivos não rastreados relevantes
3. Analise cada mudança em busca de:
   - **Bugs**: lógica incorreta, edge cases não tratados, condições invertidas
   - **Regressões**: mudanças que quebram comportamento existente
   - **Paridade TS↔Python**: se um motor mudou, o espelho também mudou?
   - **Tipos TypeScript**: rode `/types` se houver mudanças em `.ts`/`.tsx`
   - **Testes**: rode `/test` se houver mudanças em engines ou routers

4. Reporte:
   ```
   APROVADO / ATENÇÃO / BLOQUEADO

   Problemas encontrados:
   - arquivo.ts:42 — descrição do problema

   Sugestões (não bloqueantes):
   - ...
   ```

5. Se $ARGUMENTS contiver `--fix`, aplique as correções antes de reportar.
6. Se $ARGUMENTS contiver `--commit`, após aprovação crie o commit com mensagem adequada.

## Tarefa

$ARGUMENTS
