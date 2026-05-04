# Otimizacao

## Hard constraints

- Professor nao pode estar em dois lugares no mesmo slot.
- Sala nao pode ser duplicada no mesmo slot.
- Capacidade da sala precisa atender `expected_demand`.
- Professor precisa estar habilitado para a disciplina.
- Disciplina que exige laboratorio precisa de sala `lab`.
- Carga maxima contratual nao pode ser excedida.
- Carga minima docente e registrada como alerta soft de baixa prioridade; carga maxima continua hard.
- Indisponibilidade hard do professor bloqueia alocacao.
- Professor emprestado so pode ser alocado no semestre registrado no contrato.
- Professor emprestado respeita carga maxima reduzida definida pelo coordenador.
- Cadeiras compartilhadas por contexto so sao agrupadas quando possuem mesma carga total, mesma carga teorica/pratica, mesmo tipo de sala e mesma chave de contexto.
- Demanda revelada por escolhas de alunos entra no snapshot por semestre.

## Soft constraints

- Preferencia por disciplina.
- Preferencia por horario.
- Balanceamento de carga.
- Menor desperdicio de capacidade de sala.
- Menos buracos por semestre recomendado.
- Priorizacao de disciplinas criticas.

## Perfis

- `fast`: feedback interativo.
- `balanced`: padrao.
- `deep`: melhor busca para proposta final.

## Rust opcional

```bash
cargo build --manifest-path crates/optimizer/Cargo.toml --release
export OPTIGRADE_OPTIMIZER_BIN="$(pwd)/crates/optimizer/target/release/optigrade-optimizer"
```

Quando configurado, o backend passa o snapshot para o binario e compara a resposta contra os candidatos Python.

## Professores emprestados

Um professor emprestado representa disponibilidade temporaria de outro departamento ou unidade. No modelo atual, essa condicao fica em `ProfessorContract`:

- `is_borrowed=true`
- `semester` obrigatorio
- `borrowed_from_department`
- `max_hours` reduzido
- disponibilidade cadastrada pelo coordenador ou professor

Durante `build_snapshot`, contratos com `semester` diferente do semestre da `OptimizationRun` sao descartados. Isso impede que um professor emprestado apareca em grades de outros semestres.

## Demanda discente

As escolhas dos alunos em `StudentCourseRequest` sao agregadas por cadeira e `target_semester` depois da validacao discente. Durante `build_snapshot`, uma escolha so entra na demanda efetiva quando:

- a cadeira pertence ao curso do aluno ou possui equivalencia por `context_key`;
- a cadeira ainda nao foi concluida pelo aluno;
- todos os pre-requisitos hard estao atendidos pelo historico ou por cadeira equivalente.

A demanda efetiva usada para sala e agrupamento passa a ser:

```text
max(course.expected_demand, count(StudentCourseRequest por cadeira e semestre))
```

Assim, uma disciplina com demanda manual baixa pode crescer automaticamente quando muitos alunos a selecionam no formulario discente, sem aceitar pedidos academicamente bloqueados como demanda real. Os contadores aparecem em `OptimizationRun.metrics.student_demand_raw_requests`, `student_demand_requests`, `student_demand_blocked_requests`, `student_regular_requests`, `student_reoffer_requests` e `student_elective_requests`.

## Contexto academico compartilhavel

O modelo agora separa:

- campus;
- curso de graduacao;
- cadeira;
- carga horaria total;
- horas teoricas;
- horas praticas;
- contexto academico.

Ofertas compartilhaveis por `context_key` so sao agrupadas quando continuam compativeis no campus. Salas tambem possuem `campus_id`; quando cadeira e sala possuem campus definido, o solver rejeita alocacoes em campus diferente.

O campo `context_key` permite representar equivalencia academica entre cadeiras de cursos diferentes. Exemplo:

```text
Calculo A - Engenharia de Producao
Calculo A - Engenharia Civil
context_key = calculo-a:engenharias
workload_hours = 4
theoretical_hours = 4
practical_hours = 0
```

No snapshot de otimizacao, cadeiras com `shareable=true` e mesma assinatura academica sao convertidas em um unico grupo interno:

```text
(context_key, workload_hours, theoretical_hours, practical_hours, requires_lab, kind)
```

Esse grupo recebe:

- demanda agregada;
- maior criticidade entre as cadeiras de origem;
- menor semestre recomendado;
- lista de cadeiras de origem em `source_course_ids`.

Habilitacoes e preferencias docentes sao expandidas: se um professor esta habilitado para uma cadeira de origem, ele pode ministrar a oferta compartilhada. A alocacao persistida usa uma cadeira representante, enquanto `OptimizationRun.metrics.shared_course_groups` guarda a rastreabilidade do agrupamento.
