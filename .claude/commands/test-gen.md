# /test-gen — Agente gerador de testes

Gere ou atualize testes seguindo os padrões estabelecidos neste projeto.

## Onde ficam os testes

```
backend/tests/
  test_base.py              — testes de dados base
  test_auth.py              — autenticação
  test_engines.py           — endpoints de engines
  test_sequence_engine.py   — paridade TS↔Python do sequenceEngine (usa golden fixtures)
  test_placeholders.py      — paridade TS↔Python dos placeholders
  test_nipple_depth.py      — cálculo de profundidade
  test_changelog.py         — changelog de linhas
```

## Padrões observados

- Fixtures pytest em `conftest.py` (`backend/conftest.py`)
- Golden fixtures geradas por scripts TS em `abandono-app/scripts/gen*Fixtures.ts`
- Testes de paridade carregam o JSON de golden e comparam com saída do Python
- Usar `pytest.mark.parametrize` para múltiplos casos
- Rodar: `cd backend && .venv/bin/python -m pytest -q`

## Tarefa

$ARGUMENTS

1. Leia os arquivos de teste existentes mais relacionados para entender o padrão
2. Leia o código que será testado
3. Escreva os testes novos/atualizados
4. Rode `cd backend && .venv/bin/python -m pytest -q` para confirmar que passam
