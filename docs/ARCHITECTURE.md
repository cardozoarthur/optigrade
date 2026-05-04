# Arquitetura

OptiGrade usa uma arquitetura local-first, pronta para evoluir para deploy em servidor.

## Camadas

- Web: interface operacional para coordenador e portal do professor.
- API: contratos HTTP, persistencia, validacao e execucoes de otimizacao.
- Worker: orquestracao Ray para jobs paralelos e futuros pipelines assincronos.
- Optimizer: nucleo Rust opcional para busca evolutiva paralela.
- PostgreSQL: dados transacionais, auditoria e pgvector para futuras buscas semanticas.
- Modelo academico: campus, curso de graduacao e cadeira contextualizada por horas teoricas/praticas.

## Portfolio de otimizacao

O MVP nao depende de um unico solver. A execucao usa:

- precheck deterministico para inviabilidades obvias;
- agrupamento de cadeiras equivalentes por `context_key`;
- CP-SAT baseline para satisfacao forte de restricoes;
- multi-start greedy para construir solucoes viaveis;
- local search para melhorar solucoes candidatas;
- ranking por objetivos separados;
- Rust opcional como candidato adicional quando o binario estiver configurado.

O caminho para evoluir e ampliar o CP-SAT para cenarios maiores, adicionar NSGA-II com Pareto front explicito e usar Optuna para tuning automatizado de pesos e parametros.

## IA

A IA interpreta linguagem natural e produz uma DSL estruturada. A regra nao afeta a grade como texto livre: ela precisa ser armazenada, auditada e validada antes de virar constraint ativa.

Sem `OPENAI_API_KEY`, a API usa heuristicas locais. Com chave configurada, usa o modelo definido por `OPENAI_MODEL`.

## Frontend, cache e revalidacao

O frontend usa Next.js App Router com paginas publicas estaticas sempre que possivel e area operacional dinamica apenas onde a sessao por cookie e obrigatoria. A decisao segue o modelo recomendado pelo Next.js: manter layouts compartilhados em `auto`, evitar `force-dynamic` como configuracao global e controlar cache no ponto de busca de dados.

A rota BFF `/api/bff/[...path]` continua autenticada e autorizada por papel academico antes de acessar a API FastAPI. Para reduzir chamadas repetidas sem cachear dados sensiveis no navegador:

- GETs institucionais de catalogo (`campuses`, `degree-programs`, `courses`, `course-restrictions`, `professors`, `rooms`, `timeslots`) usam cache interno do Next por 300 segundos.
- `readiness` usa cache curto de 30 segundos.
- Dados de alunos, sugestoes, historico, escolhas, otimizacoes e portal por token seguem `no-store`.
- Mutacoes invalidam tags por organizacao e recurso com `revalidateTag`, por exemplo `optigrade:<org>:courses` e `optigrade:<org>:catalog`.
- As respostas BFF para o browser continuam com `Cache-Control: private, no-store` e `Vary: Cookie`; o cache fica no Data Cache interno do Next, nao no cliente.

Referencias oficiais consultadas:

- Next.js Caching and Revalidating: `fetch`, tags e `unstable_cache`.
- Next.js Route Segment Config: `dynamic`, `revalidate` e `fetchCache`.
- Next.js `revalidateTag`: invalidacao sob demanda por tag.

## Dados sensiveis

O MVP usa Better Auth com sessoes por cookie e plugin de organizacao. Links de convite usam token aleatorio e expiram. Dados protegidos passam pelo BFF autenticado antes de chegar a API interna.
