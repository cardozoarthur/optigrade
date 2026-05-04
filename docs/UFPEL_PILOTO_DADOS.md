# Dataset Piloto UFPel 2026/1

Este documento registra o dataset oficial usado no piloto do OptiGrade para cursos de Engenharia e Computacao da UFPel.

## Fontes Oficiais

- Centro de Engenharias: https://institucional.ufpel.edu.br/unidades/id/444
- Centro de Desenvolvimento Tecnologico: https://institucional.ufpel.edu.br/unidades/id/443
- Paginas oficiais de cursos no Portal Institucional UFPel, no padrao `https://institucional.ufpel.edu.br/cursos/cod/{codigo}`.
- Criterio academico de frequencia minima: https://wp.ufpel.edu.br/perguntas/frequencia/
- Regimes e carreira do Magisterio Federal: Lei 12.772/2012, https://www.planalto.gov.br/ccivil_03/_Ato2011-2014/2012/Lei/L12772compilado.htm
- Ingresso em instituicoes federais: Lei 12.711/2012, https://www.planalto.gov.br/ccivil_03/_Ato2011-2014/2012/Lei/L12711.htm

## Cursos Importados

Periodo oficial importado: `2026/1`.

### Centro de Engenharias

- `UFPEL-700` - Engenharia Agricola
- `UFPEL-6200` - Engenharia Ambiental e Sanitaria
- `UFPEL-6300` - Engenharia Civil
- `UFPEL-6900` - Engenharia de Controle e Automacao
- `UFPEL-6500` - Engenharia de Petroleo
- `UFPEL-6700` - Engenharia de Producao
- `UFPEL-7000` - Engenharia Eletronica
- `UFPEL-5600` - Engenharia Geologica
- `UFPEL-5200` - Engenharia Industrial Madeireira

### Centro de Desenvolvimento Tecnologico

- `UFPEL-3900` - Ciencia da Computacao
- `UFPEL-3910` - Engenharia de Computacao
- `UFPEL-6100` - Engenharia de Materiais
- `UFPEL-6400` - Engenharia Hidrica

## Dados Cadastrados

O importador `python -m app.ufpel_pilot_seed` cadastra:

- campus piloto `UFPel - Campus Porto`;
- cursos com unidade academica, janela de horario regular, carga horaria obrigatoria estimada pela matriz curricular e URL fonte;
- disciplinas/turmas oficiais com codigo, turma, semestre recomendado, demanda por vagas/matriculas, horario oficial e URL da disciplina;
- docentes oficiais extraidos das turmas ofertadas;
- habilitacoes docente-disciplina conforme professor responsavel/regente publicado;
- disponibilidade docente hard exatamente nos horarios oficiais importados;
- salas e laboratorios piloto dimensionados pelo pico simultaneo oficial do campus.
- alunos piloto sinteticos e anonimos, distribuidos entre todos os cursos UFPel importados;
- historico academico sintetico por aluno, com cadeiras concluidas e alguns casos de reoferta;
- escolhas de cadeiras para `2026/2`, simulando a 1ª etapa do fluxo discente.

## Criterios Modelados

- Frequencia minima de aprovacao: `75%`.
- Nota media padrao de aprovacao: `7,0`.
- Limite operacional docente usado no piloto: ate `40h` semanais.
- Cursos regulares respeitam a janela oficial/observada do curso; reofertas e coofertas seguem disponibilidade docente e capacidade de campus.
- Coofertas oficiais no mesmo docente, sala e horario sao tratadas como uma sessao compartilhada quando ha capacidade suficiente.
- Dados de alunos sao demonstrativos e nao representam estudantes reais da UFPel.
- Reofertas por equivalencia usam `context_key`: um aluno reprovado em uma cadeira compartilhavel, como Calculo A, pode solicitar turma equivalente de outro curso compativel.
- Restricoes docentes estruturadas entram no otimizador: multiplas janelas por dia, indisponibilidade hard/soft, preferencias de horario, preferencias por cadeira e carga minima/maxima contratual.
- Carga maxima docente permanece restricao hard; carga minima docente e tratada como alerta de subutilizacao de baixa prioridade, pois o docente pode cumprir ponto/atividade institucional fora da sala de aula, embora o sistema tente evitar ociosidade.
- Para semestres com formulario discente, a grade administrativa pode rodar em modo orientado por demanda, ofertando apenas cadeiras escolhidas e elegiveis.
- A matricula automatica roda junto com a geracao da grade administrativa, usando filas de alternativas do aluno no formato "X, senao Y, senao Z".
- Na visao administrativa nao existe etapa manual de rodada: ao gerar ou reotimizar, o sistema mostra o resumo pronto quando a grade e a alocacao terminam; na area do aluno aparecem as cadeiras alocadas, em espera ou bloqueadas.
- A pontuacao de vaga considera primeira tentativa, atraso curricular, reoferta/dependencia, nota de reprovação quando existir, prioridade da escolha, ordem da fila e media das notas nas dependencias da cadeira.

## Resultado do Dry-Run

Execucao em Postgres descartavel local:

- cursos UFPel efetivos cadastrados: `13`;
- disciplinas/turmas efetivas cadastradas: `672`;
- docentes cadastrados: `202`;
- salas/laboratorios piloto: `120`;
- slots oficiais distintos: `87`;
- grupos de contexto academico compartilhado: `98`;
- alunos piloto sinteticos UFPel: `156`;
- registros de historico academico sintetico: `3458`;
- escolhas sinteticas de alunos para `2026/2`: `697`;
- demandas elegiveis no fluxo discente para `2026/2`: `698` incluindo o aluno demo do seed base;
- demandas bloqueadas no fluxo discente para `2026/2`: `0`;
- dry-run de matricula automatica `2026/2`: `699` alocacoes, `0` em espera, `0` bloqueadas e `0` grupos sem alocacao;
- sessoes oficiais requeridas: `952`;
- sessoes oficiais alocadas: `952`;
- cobertura: `100%`;
- conflitos hard: `0`.

## Limitacoes Declaradas

O Portal Institucional UFPel publica cursos, matrizes, docentes e horarios das turmas, mas nao fornece neste fluxo o inventario completo de salas fisicas com capacidade e tipo. Por isso, as salas sao recursos piloto dimensionados por capacidade simultanea de campus, mantendo compatibilidade de campus e tipo teorico/laboratorio sem afirmar nomes reais de salas.
