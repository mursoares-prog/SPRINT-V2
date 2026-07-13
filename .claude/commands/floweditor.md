# /floweditor — Agente especializado no Editor de Fluxogramas (ReactFlow)

Você é especialista no editor de fluxogramas do SPRINT-V2. Leia este contexto inteiro antes de qualquer ação.

## Visão geral da arquitetura

O editor é o **único** editor de lógica ativo. Os três arquivos centrais são:

| Arquivo | Responsabilidade |
|---|---|
| `abandono-app/src/components/LogicFlowEditor.tsx` | UI ReactFlow: nós, layout, editor inline de chips |
| `abandono-app/src/components/LogicEditorPanel.tsx` | Shell: carrega escopo, gerencia histórico de undo, chama `handleEditAction` |
| `abandono-app/src/components/LogicGraphPanel.tsx` | Tipos compartilhados (`EditAction`, `ResolvedPkgList`, `MenuState`, etc.) + render SVG somente-leitura (biblioteca de impressão) |

O `LogicGraphPanel` **não é mais editor** — sobrevive apenas como componente de renderização SVG para exportação/impressão.

## Tipos de dados (fonte de verdade: `data/logicSecs.ts`)

```typescript
type LPkgPhase = 'Fase 0' | 'Fase 1A' | 'Fase 1B' | 'Fase 2' | 'Extra Abandono' | 'Mobilização' | 'Desmobilização'
type LPkg = { id: string; name: string; phase?: LPkgPhase; condition?: string; isContingency?: boolean }
type LAns = { label: string; packages?: LPkg[]; seq?: LSeqEntry[]; after?: LSeqEntry[]; sub?: LDec[]; afterSub?: LDec[]; note?: string; _pos?: ... }
type LDec = { question: string; packages?: LPkg[]; answers: LAns[]; after?: LSeqEntry[]; afterDec?: LDec[]; _pos?: ...; _convPos?: ... }
type LSec = { label: string; phase: string; color: PC; decisions: LDec[]; always?: LPkg[]; _pos?: ... }
type LSeqEntry = { label?: string; packages?: LPkg[]; sub?: LDec[]; afterSub?: LDec[] }
```

`LSec.phase` é a fase da seção — serve como fallback quando `LPkg.phase` não está definido (~255 de 309 pacotes não têm fase explícita).

## Constantes de layout (LogicFlowEditor.tsx)

```typescript
const AW   = 290   // largura do card de resposta / chip
const QW   = 280   // largura do losango de pergunta
const QH   = 46    // altura do losango
const LBLH = 22    // barra de rótulo dos chips
const BPAD = 8     // padding vertical interno dos corpos
const PKG  = 44    // altura de uma linha de pacote (código + nome em 2 linhas)
const NOTE = 15    // linha de nota / placeholder "—"
const AG   = 16    // vão horizontal entre colunas de resposta
const V_QA = 56    // pergunta → respostas
const V_SUB = 44   // resposta → sub-pergunta
const V_DEC = 58   // entre decisões sequenciais
const V_AFTER = 34 // até bloco "após convergência"
const V_CONV = 30  // ramo mais fundo → barra de convergência
const FRAME_HEADER = 42
const FRAME_PAD    = 26
const SEC_GAP      = 128  // vão vertical entre molduras de seção
const chipH = (n: number) => BPAD + (n > 0 ? n * PKG : NOTE) + BPAD
```

## Tipos de nós ReactFlow

```typescript
const NODE_TYPES = {
  framenode: FrameNode,   // moldura de seção (FData)
  qnode:     QuestionNode, // losango de pergunta (QData)
  anode:     AnswerNode,   // card de resposta (AData)
  chipnode:  ChipNode,     // chip autônomo: SEMPRE, dec.packages, dec.after, ans.seq, ans.after (ChipData)
  junction:  JunctionNode, // círculo de convergência de ramos
}
```

## Tipos de dados dos nós

```typescript
type QData  = { dec: LDec; ref: DecRef | null; pc: PC; dark: boolean; hit: boolean; dup: boolean; pick: boolean; canEdit: boolean; hasDefault: boolean }
type AData  = { ans: LAns; ref: DecRef | null; ansIdx: number; pc: PC; dark: boolean; hit: boolean; canEdit: boolean; label2?: string; secPhase?: string; onFlagPkg?: (pkgIdx: number) => void; onStar?: () => void; onFlag?: () => void }
type ChipData = { label: string; pkgs: LPkg[]; pc: PC; dark: boolean; canEdit: boolean; hit: boolean; variant: 'sempre' | 'after'; secPhase?: string; contingency?: boolean; clickable?: boolean; onFlag?: () => void; onFlagPkg?: (i: number) => void }
type FData  = { sec: LSec; secIdx: number; pc: PC; dark: boolean; hit: boolean; width: number; height: number; canEdit: boolean; expanded?: boolean; onClick?: ...; onContext?: ... }
```

## NodeMeta — endereçamento por nó

Cada clique resolve um `NodeMeta` a partir do `id` do nó:

```typescript
type NodeMeta =
  | { kind: 'sec';       secIdx: number }
  | { kind: 'sempre';    secIdx: number }
  | { kind: 'q';         ref: DecRef }
  | { kind: 'decpkg';    ref: DecRef }                   // nó chip acima do losango
  | { kind: 'a';         ref: DecRef; ansIdx: number }
  | { kind: 'decafter';  ref: DecRef; afterIdx: number }
  | { kind: 'ansfield';  ref: DecRef; ansIdx: number; ftype: 'seq' | 'after'; idx: number }
  | { kind: 'free' }                                     // somente leitura
```

## Sistema de paleta de cores

```typescript
type PC = 'gray' | 'blue' | 'amber'  // uma por seção
const pal = (dark: boolean, pc: PC): PEntry => (dark ? DARK_PAL : PAL)[pc]
// PEntry tem: { ans, ansT, ansB, code, lblT, noteT, empty, hit }
```

## Editor inline de chips (`ChipEditorCtx`)

Clicar com o botão **esquerdo** em um chip de pacotes ativa o editor inline. O estado ativo vive em `activeChip` no componente `LogicFlowEditor` e é passado via context:

```typescript
type ChipEditorCtxValue = {
  nodeId: string
  title?: string
  onTitleChange?: (v: string) => void
  items: MenuItem[]
  pkgs?: ResolvedPkgList
  pkgsRefresh?: () => LPkg[]   // lê sectionsRef.current diretamente (evita closure stale)
  onFlagPkg?: (i: number) => void
  onClose: () => void
} | null
const ChipEditorCtx = createContext<ChipEditorCtxValue>(null)
```

### `ResolvedPkgList` (em LogicGraphPanel.tsx)

```typescript
export type ResolvedPkgList = {
  list: LPkg[]
  onAdd: () => void
  onMove: (idx: number, dir: 'up' | 'down') => void   // mantido para compat
  onRemove: (idx: number) => void
  onCondition?: (idx: number, condition?: string) => void
  onPhase?: (idx: number, phase?: string) => void
  onReorder?: (from: number, to: number) => void      // usado pelo DnD
}
```

`pkgsRefresh` é essencial: `handleEditAction` usa `deepClone(sectionsRef.current)`, então chamar `fire()` múltiplas vezes no mesmo handler vê a **mesma** ref stale. Para leitura reativa dos pacotes após edição, use `pkgsRefresh()`.

### Componentes do editor inline

- **`PkgRow`** — linha de pacote somente-leitura. Props: `{ pkg, p, dark, canEdit, secPhase, onFlag? }`
- **`PkgEditRows`** — lista editável de pacotes com grip DnD + ×. Props: `{ pkgList, p, dark, secPhase?, onFlagPkg?, onCondition?, onPhase?, onReorder?, onRemove, onAdd? }`. Tem `dragIdx`/`dragOverIdx` state interno; exibe `⠿` como handle de drag.
- **`InlinePkgEditor`** — wrapper que empacota `PkgEditRows` com borda e background do chip. Usado dentro de `ChipNode`.
- **`ChipBody`** — render somente-leitura dos pacotes de um chip.

## Abreviações OW Fase

```typescript
const PHASE_ABBREV: Record<string, string> = {
  'Fase 0':         'Ap.0',
  'Fase 1A':        'Ap.1A',
  'Fase 1B':        'Ap.1B',
  'Fase 2':         'Ap.2',
  'Extra Abandono': 'Extra',
  'Mobilização':    'Mob.',
  'Desmobilização': 'Desmob.',
}
```

Fase explícita no pacote → opacity 0.85. Fase herdada da seção → opacity 0.5.

## Geração do grafo — `buildGraph` e `layoutDec`

`buildGraph(sections, dark, canEdit, ...)` é chamado em `useMemo` dentro de `LogicFlowEditor`. Internamente declara `layoutDec` como **function declaration no escopo de `buildGraph`** (não dentro do `forEach`). Isso significa que `layoutDec` é içada (hoisted) — ela não tem acesso lexical à variável `sec` do `forEach`.

**Armadilha crítica**: qualquer referência a `sec` dentro de `layoutDec` causa `ReferenceError` em runtime. A seção deve ser passada como parâmetro:

```typescript
function layoutDec(dec, cx, top, ref, pc, key, secPhase?: string): { entryId, exitIds, bottom }
// Chamada no forEach:  layoutDec(dec, cx, top, ref, pc, key, sec.phase)
// Chamadas recursivas: layoutDec(sub, cx, top, subRef, pc, key, secPhase)  // repassa parâmetro
```

## Fluxo de ações (fire → handleEditAction)

```
ChipNode / AnswerNode / QuestionNode
  └─ fire(action: EditAction)
       └─ editCb(action)  [= handleEditAction em LogicEditorPanel]
            └─ deepClone(sectionsRef.current)
                 modifica o clone com switch(action.type)
                 setSections(next)  ← NÃO usa forma funcional do setState
                 sectionsRef.current = next
```

**Consequência**: múltiplos `fire()` no mesmo handler JS veem todos a **mesma** `sectionsRef.current`. Por isso reordenação usa `p_reorder_*` (splice atômico) em vez de múltiplos `p_move_*`.

## EditAction — tipos de ação relevantes por categoria

### Pacotes de resposta (`ans.packages`)
- `p_move_pkg` · `p_reorder_pkg` · `p_add_pkg` / `p_add_pkg_direct` · `p_remove_pkg` · `p_clear_ans_pkgs`
- `p_set_pkg_condition` · `p_set_pkg_phase` · `p_toggle_ans_pkg_contingency`

### Pacotes da decisão (`dec.packages`)
- `p_move_dec_pkg` · `p_reorder_dec_pkg` · `p_add_dec_pkg` / `p_add_dec_pkg_direct` · `p_remove_dec_pkg` · `p_clear_dec_pkgs`
- `p_set_pkg_condition` (sem ansIdx) · `p_set_pkg_phase` (sem ansIdx) · `p_toggle_dec_pkg_contingency`

### SEMPRE (`sec.always`)
- `move_always` · `reorder_always` · `add_always` · `remove_always`

### Dec.after (`dec.after[i].packages`)
- `p_dec_move_after_pkg` · `p_dec_reorder_after_pkg` · `p_dec_add_after_pkg` · `p_dec_remove_after_pkg`
- `p_set_dec_after_pkg_condition` · `p_set_dec_after_pkg_phase`

### Ans.seq e ans.after
- `p_move_seq_pkg` · `p_reorder_seq_pkg` · `p_add_seq_pkg` · `p_remove_seq_pkg`
- `p_set_seq_pkg_condition` · `p_set_seq_pkg_phase`
- `p_move_after_pkg` · `p_reorder_after_pkg` · `p_add_after_pkg` · `p_remove_after_pkg`
- `p_set_after_pkg_condition` · `p_set_after_pkg_phase`

### Estruturais
- `p_set_q` · `p_set_ans` · `p_move_ans` · `p_ins_ans`
- `set_node_pos` (não entra no undo) · `clear_node_pos`
- `p_set_section_label` · `p_set_section_phase`

## Interação — clique esquerdo vs. direito

| Clique | Comportamento |
|---|---|
| Esquerdo em chip/anode com pacotes | `openChipInline` → editor inline via `ChipEditorCtx` |
| Esquerdo em qnode | `openQMenu` mode `'quick'` (editar rótulo + pacotes dec) |
| Direito em qualquer nó | menu lateral completo com ações estruturais |
| Esquerdo em framenode | editar rótulo da seção |

## Nó `ChipNode` — detalhes

- `draggable: false` no ReactFlow (sem conflito com DnD interno)
- Outline azul 2px quando `isActive` (selecionado para edição inline)
- Botão fechar `×` absoluto em `top:-9, right:-9` (fora do corpo do chip)
- Renderiza `InlinePkgEditor` quando ativo, `ChipBody` + LBLH quando não ativo

## Nó `AnswerNode` — detalhes

- `draggable: canEdit && !!ref`
- Quando `isActive`: body tem `onMouseDown={e => e.stopPropagation()}` para bloquear drag do nó
- Renderiza `PkgEditRows` direto (sem wrapper `InlinePkgEditor`) quando ativo
- `secPhase={d.secPhase}` deve ser passado tanto para `PkgEditRows` quanto para `PkgRow`

## Gotchas conhecidos

1. **Tela preta**: qualquer `ReferenceError` dentro de `buildGraph`/`layoutDec` resulta em tela preta. Verificar escopo de variáveis, especialmente `sec` × `secPhase`.
2. **picklist não abre**: `autoFocus` em `<select>` não abre o dropdown. Usar `ref` callback com `el.showPicker()` dentro de `try/catch`.
3. **DnD vs. ReactFlow**: usar classe `nodrag` em handles de drag e `e.stopPropagation()` em `onDragStart` para evitar que o ReactFlow interprete o evento como arrasto de nó.
4. **Multiple fire() calls**: nunca chamar `fire()` múltiplas vezes para reordenar — usar ação `p_reorder_*` atômica.
5. **Altura do chip**: `chipH(n)` deve ser idêntico entre `buildGraph` (layout) e render. Qualquer diferença causa drift visual.

## Tarefa

$ARGUMENTS

Leia os arquivos relevantes antes de editar. Confirme tipos com `cd abandono-app && npx tsc --noEmit` ao final.
