# PRD - OptiGrade

OptiGrade e uma plataforma de planejamento semestral de disciplinas para universidades publicas, com foco inicial na UFPel.

## Objetivo

Gerar grades otimizadas considerando restricoes institucionais, legais, docentes, discentes e de salas. O produto separa o problema em oferta de disciplinas, alocacao de salas e alocacao docente.

## Decisoes do MVP

- Previsao de demanda fica fora do MVP.
- `demanda_prevista` entra como dado manual/importado.
- Professores preenchem preferencias e restricoes por link de convite.
- Coordenadores controlam carga minima, carga maxima e habilitacoes formais.
- O solver usa portfolio multiobjetivo, nao um unico algoritmo.
- IA e usada para interpretar regras, explicar tradeoffs e diagnosticar inviabilidade, mas nao substitui o validador deterministico.

## Restricoes docentes

O professor pode declarar dias, janelas de trabalho, horarios indisponiveis, preferencias de horarios, disciplinas desejadas e disciplinas evitadas. O coordenador registra carga minima legal, carga maxima contratual e disciplinas habilitadas.

Cada regra e classificada como:

- `hard`: obrigatoria.
- `soft`: preferencia otimizada.
- `manual_override`: excecao auditavel do coordenador.

## Saida esperada

Cada execucao retorna:

- ranking de solucoes;
- score por dimensao;
- conflitos hard/soft;
- calendario final;
- explicacao de tradeoffs;
- diagnostico quando o cenario for inviavel.

