# /types — Verificação de tipos TypeScript

Rode `tsc --noEmit` no frontend e mostre apenas erros reais (sem warnings).

## Passos

1. Execute a verificação de tipos a partir de `abandono-app/`:
   ```
   cd /Users/murilo/SPRINT-V2/abandono-app && npx tsc -p tsconfig.app.json --noEmit 2>&1
   ```

2. Analise a saída:
   - Se não houver erros: informe "TypeScript OK — nenhum erro de tipo encontrado"
   - Se houver erros: agrupe-os por arquivo e liste com formato:
     ```
     src/components/Foo.tsx
       linha 42: Cannot find name 'X'
       linha 87: Type 'Y' is not assignable to type 'Z'
     ```

3. Indique o total: "N erro(s) em M arquivo(s)".

4. Se o usuário pedir, corrija os erros diretamente.
