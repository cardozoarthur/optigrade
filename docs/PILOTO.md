# Piloto OptiGrade

Este documento define o procedimento minimo para rodar um piloto controlado do OptiGrade com coordenacao, docentes e um grupo reduzido de alunos.

## Objetivo do piloto

Validar se o sistema consegue:

- cadastrar campus, cursos, cadeiras, salas, docentes e alunos;
- registrar pre-requisitos, corequisitos e historico discente;
- sugerir cadeiras elegiveis para o proximo semestre;
- coletar escolhas dos alunos;
- transformar escolhas em demanda efetiva;
- gerar uma grade viavel com `hard_conflicts = 0`;
- explicar a qualidade da solucao por metricas e ranking.

## Escopo recomendado

Para o primeiro piloto, use um recorte pequeno:

- 1 campus;
- 1 ou 2 cursos;
- 8 a 15 cadeiras;
- 5 a 10 professores;
- 4 a 8 salas;
- 20 a 80 alunos reais ou anonimizados;
- 1 semestre alvo, por exemplo `2026/2`.

Evite iniciar com toda a universidade. O objetivo inicial e validar o fluxo operacional, nao resolver a escala maxima no primeiro dia.

## Preparacao

1. Subir PostgreSQL:

```bash
docker compose up -d postgres
```

2. Rodar migracoes:

```bash
pnpm migrate
```

3. Inserir dados iniciais, se o banco estiver vazio:

```bash
pnpm seed
```

4. Subir API e frontend. Para o ambiente desta maquina, o piloto esta sendo validado em:

```bash
API_CORS_ORIGINS=http://localhost:3301,http://127.0.0.1:3301 UV_CACHE_DIR=.uv-cache uv run uvicorn app.main:app --host 0.0.0.0 --port 8002
NEXT_PUBLIC_API_URL=http://localhost:8002 pnpm --filter @optigrade/web exec next dev --hostname 0.0.0.0 --port 3301
```

5. Abrir:

```text
http://localhost:3301
```

## Gate tecnico

Antes de demonstrar para usuarios, rode:

```bash
API_URL=http://127.0.0.1:8002 WEB_URL=http://127.0.0.1:3301 pnpm pilot:check
```

O comando executa:

- toolchain check;
- migracoes Alembic;
- compileall Python;
- ruff;
- pytest;
- typecheck TypeScript;
- Vitest;
- build Next.js;
- cargo test;
- `GET /health`;
- `GET /readiness`;
- smoke E2E com aluno, historico, requisito, escolha e otimizacao.

Para rodar somente o fluxo funcional contra servicos ja ativos:

```bash
API_URL=http://127.0.0.1:8002 pnpm pilot:smoke
```

## Readiness da API

Use:

```bash
curl -fsS "http://127.0.0.1:8002/readiness?semester=2026/2"
```

Resposta esperada:

```json
{
  "status": "ready",
  "database": "ok",
  "missing_required_data": [],
  "optimization_precheck": []
}
```

Se `status` vier como `degraded`, leia:

- `missing_required_data`: dados minimos ausentes;
- `optimization_precheck`: cursos sem professor habilitado, salas insuficientes ou outras inviabilidades antes da busca.

## Roteiro de demonstracao

1. Dashboard
   - Verificar contadores de alunos, docentes, contextos e professores emprestados.

2. Cadastro academico
   - Cadastrar campus.
   - Cadastrar curso.
   - Cadastrar cadeira com carga total, horas teoricas, horas praticas, campus, curso e `context_key`.

3. Professor
   - Cadastrar professor.
   - Registrar contrato/carga.
   - Registrar habilitacao para cadeira.
   - Opcional: cadastrar professor emprestado para o semestre alvo.

4. Aluno
   - Cadastrar aluno vinculado ao curso.
   - Registrar historico de cadeiras concluidas.
   - Cadastrar pre-requisito ou corequisito.
   - Gerar sugestoes.
   - Registrar escolhas.

5. Otimizacao
   - Rodar perfil `fast` para demonstracao rapida.
   - Rodar `balanced` para uma solucao melhor.
   - Confirmar `hard_conflicts = 0`.
   - Conferir calendario e ranking de solucoes.

## Criterios de aceite do piloto

O piloto e considerado operacional quando:

- `pnpm pilot:check` passa;
- `/readiness` retorna `status = ready`;
- uma grade e gerada com `hard_conflicts = 0`;
- escolhas de alunos aparecem em `student_demand_requests`;
- professores emprestados aparecem apenas no semestre do contrato;
- cadeiras equivalentes por `context_key` sao agrupadas no snapshot;
- historico equivalente por `context_key` satisfaz pre-requisito discente;
- coordenador consegue fazer ajuste manual e reotimizar.

## Limitacoes assumidas

- Previsao de demanda por ML nao faz parte do MVP.
- Importacao institucional oficial ainda depende do formato real do sistema academico.
- Autenticacao final de usuarios ainda deve ser definida antes de producao.
- O piloto usa dados reais somente se houver autorizacao institucional; caso contrario, usar dados anonimizados.

## Evidencias a guardar

Durante o piloto, registre:

- data e semestre alvo;
- conjunto de cursos e cadeiras;
- numero de alunos com escolhas;
- numero de professores e professores emprestados;
- tempo de geracao;
- `hard_conflicts`;
- score;
- taxa de cobertura;
- observacoes de coordenadores e docentes.

## Rollback operacional

Se a grade gerada for inadequada para uso real:

- exporte ou fotografe a grade manual atual;
- use a grade do OptiGrade apenas como simulacao;
- corrija dados de entrada ou restricoes;
- rode nova otimizacao;
- nao publique para alunos ate `hard_conflicts = 0` e validacao humana da coordenacao.
