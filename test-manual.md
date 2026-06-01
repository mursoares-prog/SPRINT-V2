# Teste Manual - Realce de Pacotes na Etapa 2

## Preparação
- ✅ App rodando em http://localhost:5173
- ✅ Build compilado com sucesso (sem erros)

## Teste Esperado

### Pré-condição
1. Acessar o app em http://localhost:5173
2. Completar o wizard (etapas 1) com dados mínimos
3. Chegar na Etapa 2 (ScheduleView) com cronograma visível

### Ação Principal
1. Abrir o painel de inputs (InputSummaryPanel) 
2. Alterar um input que modifique o schedule (ex: "Escopo", "Contingência", etc)
3. Observar a tabela de cronograma

### Resultado Esperado
✅ **Imediato (quando o input é alterado):**
- Pacotes afetados devem ser realçados com:
  - Fundo: `bg-amber-200` (light) ou `bg-amber-700/70` (dark)
  - Borda: outline amarela `outline-amber-500` (light) ou `outline-amber-400` (dark)
  - Font: `font-medium`
- As fases dos pacotes realçados devem ser automaticamente expandidas
- A tela deve fazer scroll para mostrar o primeiro pacote realçado

✅ **Após 5 segundos:**
- O realce deve desaparecer automaticamente
- O estilo das linhas volta ao normal

## Implementação Verificada

### Mudanças no ScheduleView.tsx:

1. **Estado de rastreamento:**
   ```tsx
   const [highlightedUids, setHighlightedUids] = useState<Set<string>>(new Set())
   const prevItemsRef = useRef<ScheduleItem[]>(items)
   const containerRef = useRef<HTMLDivElement>(null)
   ```

2. **Detecção de mudanças:**
   ```tsx
   useEffect(() => {
     // Compara schedule anterior com novo
     // Detecta pacotes que mudaram (packageId ou duration)
     // Marca para realce
     // Expande fases
     // Faz scroll
     // Timer de 5 segundos para limpar
   }, [items])
   ```

3. **Renderização do realce:**
   ```tsx
   <tr data-uid={item.uid} className={`...
     ${highlightedUids.has(item.uid) ? 'bg-amber-200 dark:bg-amber-700/70 outline outline-2 -outline-offset-2 outline-amber-500 dark:outline-amber-400 font-medium' : ''}
   ...`}>
   ```

## Checklist de Verificação

- [x] Código compila sem erros
- [x] Sem warnings de TypeScript
- [x] Refs e states declarados corretamente
- [x] Effect de detecção de mudanças implementado
- [x] Classes CSS de realce aplicadas (mesmo estilo da etapa 3)
- [x] Timer de 5 segundos implementado
- [x] Scroll automático com `scrollIntoView`
- [x] Expansão de fases implementada

## Observações Técnicas

- O realce usa o mesmo padrão visual da etapa 3 (FineTuningView) quando um item está "em revisão"
- A detecção de mudanças compara o schedule anterior com o novo usando Maps
- O scroll é suave (`behavior: 'smooth'`) e só ocorre se o elemento não está visível
- O timer é automaticamente limpo se novos pacotes forem realçados (cleanup do effect)
