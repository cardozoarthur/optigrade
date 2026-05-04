# API

Base local: `http://localhost:8000`

## Coordenador

- `GET /campuses`
- `POST /campuses`
- `GET /campuses/{id}`
- `PUT /campuses/{id}`
- `DELETE /campuses/{id}`
- `GET /degree-programs`
- `POST /degree-programs`
- `GET /degree-programs/{id}`
- `PUT /degree-programs/{id}`
- `DELETE /degree-programs/{id}`
- `GET /courses`
- `POST /courses`
- `GET /students`
- `POST /students`
- `GET /students/{id}/history`
- `POST /students/{id}/history`
- `GET /students/{id}/suggestions`
- `POST /students/{id}/course-requests`
- `GET /students/{id}/course-requests`
- `GET /course-restrictions`
- `POST /course-restrictions`
- `GET /professors`
- `POST /professors`
- `POST /professors/borrowed`
- `POST /professors/{id}/contract`
- `POST /professors/{id}/qualifications`
- `POST /professors/{id}/invitations`
- `GET /rooms`
- `POST /rooms`
- `GET /timeslots`
- `POST /timeslots`

## Otimizacao

- `POST /optimization/runs`
- `GET /optimization/runs`
- `GET /optimization/runs/{id}`
- `GET /optimization/runs/{id}/assignments`
- `POST /optimization/runs/{id}/manual-adjustments`
- `POST /optimization/runs/{id}/reoptimize`

As chamadas `POST /optimization/runs` e `POST /optimization/runs/{id}/reoptimize` sao exclusivamente assincronas. Elas criam ou reutilizam uma `OptimizationRun` ativa, retornam imediatamente com status `pending` ou `running`, e a execucao ocorre em background. Clientes devem consultar `GET /optimization/runs/{id}` ate `finished_at` ser preenchido ou o status chegar em `feasible`, `infeasible` ou `failed`; somente depois disso os `assignments` representam o calendario final.

## Apresentacao academica

- `GET /presentation/stats`
- `POST /presentation/teacher-link`
- `POST /presentation/teacher-link/{token}/revoke`
- `POST /presentation/student-link`
- `POST /presentation/student-link/{token}/revoke`
- `GET /presentation/student-tokens/{token}`
- `POST /presentation/student-tokens/{token}/students`
- `POST /presentation/student-tokens/{token}/students/{student_id}/choices`

As rotas `/presentation/*` ficam atras do BFF autenticado para o apresentador administrador, exceto o fluxo de alunos, que e exposto pelo Next.js em `/api/trabalho/alunos/*` e validado por token temporario.

## Portal do professor

- `GET /teacher-portal/{token}`
- `POST /teacher-portal/{token}/submit`

## Professores emprestados

Professores emprestados sao cadastrados com `POST /professors/borrowed`. Eles recebem um contrato semestral com `is_borrowed=true`, `semester`, `borrowed_from_department` e carga reduzida em `max_hours`.

O solver so considera esse professor em execucoes cujo `semester` seja igual ao semestre do contrato. Fora desse semestre, suas habilitacoes, preferencias e disponibilidade sao ignoradas no snapshot de otimizacao.

## Planejamento discente

O fluxo discente modela a demanda de baixo para cima:

- `Student`: aluno, matricula, curso e semestre atual.
- `StudentCourseHistory`: historico de cadeiras cursadas, status e nota.
- `CourseRestriction`: pre-requisitos ou corequisitos entre cadeiras.
- `StudentCourseRequest`: escolhas do aluno para o proximo semestre.

`GET /students/{id}/suggestions?target_semester=2026/2` retorna cadeiras do curso do aluno e cadeiras institucionais sem curso, exclui cadeiras ja concluidas, reconhece conclusoes equivalentes por `context_key`, verifica pre-requisitos e rankeia sugestoes por semestre recomendado, obrigatoriedade e criticidade. Cadeiras bloqueadas aparecem com `eligible=false` e lista de requisitos faltantes. Cada sugestao tambem informa `regular_relation` e `is_regular_for_student`, permitindo comparar o formulario do aluno com as cadeiras regulares do semestre planejado.

`POST /students/{id}/course-requests` registra as escolhas do aluno. No `build_snapshot`, apenas escolhas elegiveis depois da verificacao de historico e pre-requisitos hard viram demanda efetiva. O otimizador separa demanda bruta, demanda elegivel, escolhas bloqueadas, regulares, reofertas e optativas em `OptimizationRun.metrics`.

## Contexto academico

Campus e curso de graduacao sao entidades proprias:

- `Campus`: `name`, `city`
- `DegreeProgram`: `name`, `code`, `department`, `campus_id`
- `Room`: `name`, `campus_id`, `capacity`, `kind`

Uma cadeira em `POST /courses` aceita os campos:

- `code`
- `campus_id`
- `degree_program_id`
- `workload_hours`
- `theoretical_hours`
- `practical_hours`
- `context_key`
- `shareable`

`context_key` identifica equivalencia academica. Exemplo: duas cadeiras `Calculo A`, uma da Engenharia de Producao e outra da Engenharia Civil, podem usar `context_key="calculo-a:engenharias"` quando possuem mesma carga total, mesma carga teorica/pratica e mesmo tipo de sala. Se `shareable=true`, o snapshot do solver agrega essas cadeiras em uma oferta compartilhada dentro do mesmo campus, soma a demanda e expande habilitacoes docentes de qualquer cadeira origem para o grupo compartilhado. A alocacao em sala exige campus compativel quando cadeira e sala possuem `campus_id`.

## Importacao

- `POST /imports/csv/courses`
- `POST /imports/csv/professors`
- `POST /imports/csv/rooms`
- `POST /imports/csv/timeslots`
