"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useRouter, useSearchParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Database,
  ExternalLink,
  Github,
  GraduationCap,
  Info,
  Loader2,
  Play,
  School,
  UserRoundCog,
  Users,
  X
} from "lucide-react";
import {
  Assignment,
  AssignmentDetail,
  AssignmentEnrollmentDetail,
  Campus,
  Course,
  OptimizationRun,
  Professor,
  Room,
  TimeSlot,
  dayLabels,
  minutesToLabel,
  publicPresentationApi
} from "@/lib/api";
import {
  TrabalhoSlideSlug,
  nextSlide,
  previousSlide,
  slideBySlug,
  trabalhoSlides
} from "./presentation-data";
import { usePresentation } from "./presentation-store";
import { ThreeNetworkScene } from "./three-network-scene";

export function PresentationDeck({ slug }: { slug: TrabalhoSlideSlug }) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const {
    revokeTeacherLink,
    revokeStudentLink,
    startOptimization
  } = usePresentation();
  const slide = slideBySlug(slug);
  const progress = (slide.index / trabalhoSlides.length) * 100;
  const scrollableSlide = slug === "resultado";

  const goTo = useCallback(
    (nextSlug: TrabalhoSlideSlug) => {
      void (async () => {
        if (slug === "professor" && nextSlug !== "professor") {
          await revokeTeacherLink().catch(console.error);
        }
        if (slug === "alunos" && nextSlug !== "alunos") {
          await revokeStudentLink().catch(console.error);
        }
        if (slug === "parametros" && nextSlug !== "parametros") {
          await startOptimization().catch(console.error);
        }
        router.push(`/trabalho/${nextSlug}`);
      })();
    },
    [revokeStudentLink, revokeTeacherLink, router, slug, startOptimization]
  );
  const goNext = useCallback(() => goTo(nextSlide(slug)), [goTo, slug]);
  const goPrevious = useCallback(() => goTo(previousSlide(slug)), [goTo, slug]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (["Enter", " ", "ArrowRight"].includes(event.key)) {
        event.preventDefault();
        advance(rootRef.current, goNext);
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        retreat(rootRef.current, goPrevious);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goNext, goPrevious]);

  return (
    <main
      ref={rootRef}
      className="h-screen overflow-y-auto bg-[#f6f8fb] text-ink lg:overflow-hidden"
      style={{
        backgroundImage:
          "linear-gradient(135deg, rgba(27,107,147,0.08), transparent 28%), linear-gradient(315deg, rgba(63,125,88,0.09), transparent 34%)"
      }}
    >
      <div className="fixed inset-x-0 top-0 z-20 h-1 bg-slateLine">
        <motion.div className="h-full bg-lake" animate={{ width: `${progress}%` }} transition={{ duration: 0.35 }} />
      </div>
      <header className="fixed inset-x-0 top-1 z-20 border-b border-white/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-normal text-lake">{slide.eyebrow}</p>
            <h1 className="truncate text-base font-semibold sm:text-lg">{slide.title}</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => retreat(rootRef.current, goPrevious)}
              className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-md border border-slateLine bg-white transition hover:-translate-y-0.5 hover:border-lake hover:text-lake"
              aria-label="Slide anterior"
            >
              <ArrowLeft size={18} />
            </button>
            <span className="hidden rounded-md border border-slateLine bg-white px-3 py-2 text-xs font-semibold text-slate-600 sm:inline-flex">
              {slide.index}/{trabalhoSlides.length}
            </span>
            <button
              type="button"
              onClick={() => advance(rootRef.current, goNext)}
              className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-md border border-slateLine bg-white transition hover:-translate-y-0.5 hover:border-lake hover:text-lake"
              aria-label="Próximo slide"
            >
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </header>

      <AnimatePresence mode="wait">
        <motion.section
          key={slug}
          initial={{ opacity: 0, y: 18, scale: 0.985 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -16, scale: 0.99 }}
          transition={{ duration: 0.36, ease: [0.22, 1, 0.36, 1] }}
          className={`mx-auto grid min-h-screen max-w-7xl px-4 pt-20 sm:px-6 lg:h-screen ${
            scrollableSlide
              ? "content-start overflow-y-auto overscroll-contain pb-8 [scrollbar-gutter:stable]"
              : "content-center overflow-y-auto pb-6 lg:overflow-hidden lg:pb-4"
          }`}
        >
          <SlideContent slug={slug} onNext={goNext} />
        </motion.section>
      </AnimatePresence>
    </main>
  );
}

function advance(root: HTMLElement | null, fallback: () => void) {
  if (root) {
    const required = Array.from(
      root.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
        "input[required], select[required], textarea[required]"
      )
    );
    const invalid = required.find((field) => !field.checkValidity());
    if (invalid) {
      invalid.focus();
      invalid.reportValidity();
      return;
    }
    const action = root.querySelector<HTMLButtonElement>("[data-slide-primary]");
    if (action && !action.disabled) {
      action.click();
      return;
    }
  }
  fallback();
}

function retreat(root: HTMLElement | null, fallback: () => void) {
  if (root) {
    const action = root.querySelector<HTMLButtonElement>("[data-slide-secondary]");
    if (action && !action.disabled) {
      action.click();
      return;
    }
  }
  fallback();
}

function SlideContent({ slug, onNext }: { slug: TrabalhoSlideSlug; onNext: () => void }) {
  switch (slug) {
    case "apresentacao":
      return <OpeningSlide />;
    case "contexto-historico":
      return <HistorySlide />;
    case "problema-air-new-zealand":
      return <AirProblemSlide />;
    case "solucao-air-new-zealand":
      return <AirSolutionSlide />;
    case "conclusao-artigo":
      return <ArticleConclusionSlide />;
    case "problema-optigrade":
      return <OptigradeProblemSlide />;
    case "projeto-optigrade":
      return <ProjectSlide />;
    case "professor":
      return <TeacherSlide onNext={onNext} />;
    case "alunos":
      return <StudentQrSlide onNext={onNext} />;
    case "parametros":
      return <ParametersSlide onNext={onNext} />;
    case "fluxo-otimizacao":
      return <OptimizationFlowSlide onNext={onNext} />;
    case "comparacao":
      return <ComparisonSlide />;
    case "resultado":
      return <ResultSlide />;
    case "conclusao":
      return <FinalSlide />;
  }
}

function OpeningSlide() {
  return (
    <TwoColumn
      visual={<ThreeNetworkScene mode="comparison" />}
      eyebrow="OptiGrade"
      title="Pesquisa Operacional aplicada à oferta de disciplinas"
      body="Arthur Gomes de Freitas Cardozo, aluno de Engenharia de Produção na Universidade Federal de Pelotas."
      stats={[
        ["Base teórica", "Air New Zealand"],
        ["Domínio", "Grade universitária"],
        ["Entrega", "MVP piloto"]
      ]}
    />
  );
}

function HistorySlide() {
  return (
    <NarrativeSlide
      icon={BookOpen}
      title="O artigo nasce no momento em que otimização vira sistema de produção"
      lead="Entre 1986 e 1999, a Air New Zealand saiu de planejamento manual para oito sistemas baseados em otimização."
      points={[
        "Na década de 1980, muitas tentativas em companhias aéreas falhavam por método e potência computacional insuficientes.",
        "O avanço de programação inteira, geração de colunas, branch-and-bound e workstations Unix tornou instâncias reais viáveis.",
        "A Pesquisa Operacional deixou de ser apenas análise acadêmica e virou infraestrutura operacional com impacto financeiro auditável."
      ]}
    />
  );
}

function AirProblemSlide() {
  return (
    <TwoColumn
      visual={<ThreeNetworkScene mode="air" />}
      eyebrow="Problema original"
      title="Cobrir todos os voos respeitando contratos, descanso, bases e preferências"
      body="O problema era dividido em planejamento de tours-of-duty e rostering. Cada decisão precisava ser legal, viável, robusta e aceitável para tripulações com regras diferentes."
      stats={[
        ["Tripulantes", "+2.000"],
        ["Grupos", "4 grandes tipos"],
        ["Risco", "voos sem cobertura"]
      ]}
    />
  );
}

function AirSolutionSlide() {
  return (
    <section className="grid max-h-full gap-4 lg:grid-cols-[1fr_380px]">
      <div className="grid gap-4">
        <h2 className="max-w-3xl text-3xl font-semibold leading-tight sm:text-5xl">
          A solução foi separar, gerar combinações legais e escolher o conjunto ótimo.
        </h2>
        <p className="max-w-3xl text-lg leading-relaxed text-slate-700">
          O núcleo matemático foi a partição de conjuntos: cada coluna representa uma sequência possível,
          e as restrições garantem cobertura exata de voos ou atividades.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <MetricTile label="Sistemas" value="8" />
          <MetricTile label="Custo aproximado" value="NZ$ 2 mi" />
          <MetricTile label="Economia anual" value="NZ$ 15,655 mi" tone="green" />
        </div>
      </div>
      <ImpactPanel />
    </section>
  );
}

function ArticleConclusionSlide() {
  return (
    <NarrativeSlide
      icon={CheckCircle2}
      title="Para a época, foi uma solução excepcional"
      lead="O artigo mostra um caso raro de Pesquisa Operacional integrada com usuários, contratos e decisão estratégica."
      points={[
        "A solução era sofisticada para o hardware e os solvers disponíveis.",
        "O custo de desenvolvimento foi pequeno diante da economia anual recorrente.",
        "Hoje seria possível ampliar com reotimização contínua, interfaces web, execução paralela, modelos híbridos e coleta direta de preferências."
      ]}
    />
  );
}

function OptigradeProblemSlide() {
  return (
    <section className="grid max-h-full gap-4 lg:grid-cols-[360px_1fr]">
      <Panel>
        <GraduationCap size={34} className="text-lake" />
        <h2 className="mt-4 text-2xl font-semibold">O problema aparece no atraso do aluno.</h2>
        <p className="mt-4 text-sm leading-relaxed text-slate-700">
          Um caso concreto é a tentativa de recuperar Cálculo A por três semestres após reprovação no
          primeiro semestre, causada pela entrada depois do início das aulas e pela perda de uma parte
          essencial da matéria.
        </p>
      </Panel>
      <div className="grid content-center gap-3">
        {[
          "A oferta regular nem sempre encaixa com dependências e horários.",
          "Reofertas poderiam ser compartilhadas entre cursos equivalentes.",
          "A trajetória do aluno deve alimentar a demanda, não ser tratada como ruído.",
          "A universidade precisa otimizar recursos públicos sem apagar restrições humanas."
        ].map((item, index) => (
          <motion.div
            key={item}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.08 }}
            className="rounded-md border border-slateLine bg-white px-4 py-4 shadow-panel"
          >
            {item}
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function ProjectSlide() {
  return (
    <TwoColumn
      visual={<ThreeNetworkScene mode="university" />}
      eyebrow="OptiGrade"
      title="Um sistema aberto para planejar oferta, docentes, salas e matrícula"
      body="O projeto transforma preferências de alunos e professores em restrições e objetivos de otimização, comparando cenários e gerando calendários por curso."
      stats={[
        ["GitHub", "cardozoarthur/optigrade"],
        ["Licença", "MIT"],
        ["Objetivo", "MVP piloto UFPel"]
      ]}
      link="https://github.com/cardozoarthur/optigrade"
    />
  );
}

function TeacherSlide({ onNext }: { onNext: () => void }) {
  const { teacherLink, createTeacherLink } = usePresentation();
  useEffect(() => {
    createTeacherLink().catch(console.error);
  }, [createTeacherLink]);
  return (
    <QrSlide
      title="Professor: registrar preferências e restrições complexas"
      subtitle="O QR Code abre um magic link diretamente no perfil da professora STEFFANI NIKOLI DAPPER e fica válido apenas enquanto este slide estiver ativo."
      link={teacherLink?.url}
      video="/trabalho/videos/professor-preferencias.mp4"
      onNext={onNext}
    />
  );
}

function StudentQrSlide({ onNext }: { onNext: () => void }) {
  const { studentLink, createStudentLink } = usePresentation();
  useEffect(() => {
    createStudentLink().catch(console.error);
  }, [createStudentLink]);
  return (
    <QrSlide
      title="Alunos: formar a demanda do próximo semestre"
      subtitle="Cada aluno de teste recebe histórico aleatório em Engenharia de Produção e envia uma fila de preferências."
      link={studentLink?.url}
      video="/trabalho/videos/aluno-escolhas.mp4"
      onNext={onNext}
    />
  );
}

function ParametersSlide({ onNext }: { onNext: () => void }) {
  const { stats, loadStats } = usePresentation();
  useEffect(() => {
    loadStats().catch(console.error);
  }, [loadStats]);
  return (
    <section className="grid max-h-full gap-4">
      <div>
        <p className="text-sm font-semibold uppercase text-lake">Antes de otimizar</p>
        <h2 className="mt-2 max-w-4xl text-3xl font-semibold leading-tight sm:text-5xl">
          O sistema vai buscar uma grade sem conflitos, baseada no que alunos e professores informaram.
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Dados lidos da API em tempo real
          {stats?.updated_at ? ` · ${new Date(stats.updated_at).toLocaleTimeString("pt-BR")}` : ""}.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <StatFromApi label="Cursos" value={stats?.degree_programs} icon={School} />
        <StatFromApi label="Unidades" value={stats?.campuses} icon={Database} />
        <StatFromApi label="Professores" value={stats?.professors} icon={Users} />
        <StatFromApi label="Alunos" value={stats?.students} icon={GraduationCap} />
        <StatFromApi label="Alunos/docente" value={stats?.student_teacher_ratio} suffix="x" icon={GraduationCap} warning={Boolean(stats?.students_needed_for_minimum)} />
        <StatFromApi label="Cadeiras" value={stats?.courses} icon={BookOpen} />
        <StatFromApi label="Salas" value={stats?.rooms} icon={CalendarDays} />
        <StatFromApi label="Threads" value={stats?.threads} icon={Cpu} />
        <StatFromApi label="Memória MB" value={stats?.memory_total_mb ?? undefined} icon={Database} />
        <StatFromApi label="Meta alunos" value={stats?.minimum_student_target} icon={Users} warning={Boolean(stats?.students_needed_for_minimum)} />
      </div>
      {stats?.students_needed_for_minimum ? (
        <div className="rounded-md border border-amber/30 bg-amber/10 px-4 py-2 text-sm text-amber">
          Faltam {stats.students_needed_for_minimum} alunos para a proporção mínima de 10 alunos por professor.
        </div>
      ) : null}
      <div className="flex justify-end">
        <button
          type="button"
          data-slide-primary
          onClick={onNext}
          className="focus-ring inline-flex h-11 items-center gap-2 rounded-md bg-ink px-5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-lake"
        >
          <Play size={17} />
          Iniciar otimização ao avançar
        </button>
      </div>
    </section>
  );
}

function ComparisonSlide() {
  return (
    <section className="grid max-h-full gap-4 lg:grid-cols-[1fr_1fr]">
      <ComparisonColumn
        title="Air New Zealand"
        items={[
          "Set-partitioning para tours-of-duty e rostering.",
          "Foco primário em custo, cobertura, legalidade e preferências de tripulação.",
          "Sistemas específicos por tipo de tripulação, integrados ao ambiente operacional.",
          "Ponto forte: economia auditada e robustez de produção.",
          "Limite: alto custo de especialização e menor interação direta em tempo real."
        ]}
      />
      <ComparisonColumn
        title="OptiGrade"
        items={[
          "Separação entre planejamento de oferta, alocação docente e matrícula automática.",
          "Portfólio com precheck, CP-SAT, multi-start greedy, busca local, Rust opcional e ranking Pareto.",
          "Entrada direta de professores e alunos por formulários e QR temporário.",
          "Ponto forte: demanda estudantil vira dado de otimização.",
          "Limite: MVP acadêmico ainda menor que uma operação aérea industrial."
        ]}
      />
    </section>
  );
}

function OptimizationFlowSlide({ onNext }: { onNext: () => void }) {
  const [activeStep, setActiveStep] = useState(0);
  const steps = [
    {
      title: "Piso obrigatório",
      text: "Primeiro o sistema identifica as disciplinas regulares que precisam existir: aluno no semestre certo, pré-requisitos cumpridos e turno oficial do curso.",
      icon: GraduationCap
    },
    {
      title: "Demanda estudantil",
      text: "Depois lê as filas de preferência dos alunos, inclusive escolhas compostas do tipo quero X, senão Y e Z.",
      icon: Users
    },
    {
      title: "Equivalências",
      text: "Cadeiras com mesmo contexto acadêmico, carga horária e conteúdo compatível podem ser agrupadas entre cursos antes de abrir turmas pequenas.",
      icon: BookOpen
    },
    {
      title: "Tamanho das turmas",
      text: "O solver evita sobras de 1 ou 2 alunos, redistribui demanda e divide turmas de forma balanceada conforme capacidade real das salas.",
      icon: CalendarDays
    },
    {
      title: "Agenda e docentes",
      text: "A grade é montada respeitando sala, professor, disponibilidade, habilitação, laboratório, carga máxima e restrições complexas.",
      icon: CheckCircle2
    },
    {
      title: "Matrícula automática",
      text: "Por fim, a alocação usa pontuação, atraso, reprovação e notas das dependências, com resgate para não deixar aluno sem semestre.",
      icon: Cpu
    }
  ];
  const step = steps[activeStep];
  const Icon = step.icon;
  const isLastStep = activeStep === steps.length - 1;
  const goForward = () => {
    if (isLastStep) {
      onNext();
      return;
    }
    setActiveStep((current) => Math.min(current + 1, steps.length - 1));
  };
  const goBack = () => setActiveStep((current) => Math.max(current - 1, 0));

  return (
    <section className="grid max-h-full gap-4 lg:grid-cols-[0.78fr_1fr] lg:items-center">
      <div className="max-w-4xl">
        <p className="text-sm font-semibold uppercase text-lake">Ordem de execução</p>
        <h2 className="mt-2 text-3xl font-semibold leading-tight sm:text-5xl">
          O problema é quebrado em decisões menores antes da grade final.
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-700">
          A estratégia segue a lógica da Pesquisa Operacional: fixar o que não pode faltar,
          reduzir alternativas equivalentes e só então otimizar horários, salas, professores e matrícula.
        </p>
        <div className="mt-5 grid gap-2">
          {steps.map((item, index) => (
            <button
              key={item.title}
              type="button"
              onClick={() => setActiveStep(index)}
              className={`focus-ring flex h-10 items-center gap-3 rounded-md border px-3 text-left text-sm transition ${
                index === activeStep
                  ? "border-lake bg-white text-ink shadow-panel"
                  : "border-slateLine bg-white/70 text-slate-500 hover:border-lake/50 hover:text-ink"
              }`}
            >
              <span className={`grid h-6 w-6 place-items-center rounded-md text-xs font-semibold ${
                index === activeStep ? "bg-lake text-white" : "bg-slate-100"
              }`}>
                {index + 1}
              </span>
              <span className="truncate">{item.title}</span>
            </button>
          ))}
        </div>
      </div>

      <Panel className="grid min-h-[360px] content-between overflow-hidden p-0 sm:min-h-[420px]">
        <AnimatePresence mode="wait">
          <motion.div
            key={step.title}
            initial={{ opacity: 0, x: 36, scale: 0.98 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: -28, scale: 0.99 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="grid min-h-[300px] content-center gap-5 p-6 sm:p-8"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="grid h-14 w-14 place-items-center rounded-md bg-lake/10 text-lake">
                <Icon size={28} />
              </div>
              <div className="rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
                Etapa {activeStep + 1}/{steps.length}
              </div>
            </div>
            <div>
              <h3 className="text-3xl font-semibold leading-tight sm:text-5xl">{step.title}</h3>
              <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-700 sm:text-lg">{step.text}</p>
            </div>
            {isLastStep ? (
              <div className="rounded-md border border-moss/25 bg-moss/10 px-4 py-3 text-sm leading-relaxed text-slate-700">
                No run final do piloto, essa sequência fechou com 0 conflitos hard, 0 demandas pendentes,
                0 turmas abaixo do mínimo e 0 alunos sem matrícula após a etapa de resgate.
              </div>
            ) : null}
          </motion.div>
        </AnimatePresence>
        <div className="flex items-center justify-between gap-3 border-t border-slateLine bg-slate-50 px-4 py-3">
          <button
            type="button"
            data-slide-secondary={activeStep > 0 ? true : undefined}
            onClick={goBack}
            disabled={activeStep === 0}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-slateLine bg-white px-3 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:border-lake hover:text-lake disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:border-slateLine disabled:hover:text-slate-700"
          >
            <ArrowLeft size={16} />
            Voltar etapa
          </button>
          <button
            type="button"
            data-slide-primary
            onClick={goForward}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-lake"
          >
            {isLastStep ? "Comparar projetos" : "Próxima etapa"}
            <ArrowRight size={16} />
          </button>
        </div>
      </Panel>
    </section>
  );
}

function ResultSlide() {
  const searchParams = useSearchParams();
  const {
    run,
    assignments,
    assignmentDetails,
    optimizationStartedAt,
    optimizationError,
    startOptimization,
    refreshOptimization
  } = usePresentation();
  const [elapsed, setElapsed] = useState(0);
  const [catalog, setCatalog] = useState<CalendarCatalog | null>(null);
  const running = !run || run.status === "pending" || run.status === "running";
  const runId = run?.id;
  const runStatus = run?.status;
  const explicitRunId = searchParams.get("runId");

  useEffect(() => {
    if (explicitRunId && explicitRunId !== runId) {
      refreshOptimization(explicitRunId).catch(console.error);
      return;
    }
    if (!runId || !runStatus) {
      startOptimization().catch(console.error);
      return;
    }

    refreshOptimization(runId).catch(console.error);
    if (runStatus !== "pending" && runStatus !== "running") return;

    const poll = window.setInterval(() => refreshOptimization(runId).catch(console.error), 120000);
    return () => window.clearInterval(poll);
  }, [explicitRunId, refreshOptimization, runId, runStatus, startOptimization]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setElapsed(optimizationStartedAt ? Math.floor((Date.now() - optimizationStartedAt) / 1000) : 0);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [optimizationStartedAt]);

  useEffect(() => {
    Promise.all([
      publicPresentationApi<Course[]>("/courses"),
      publicPresentationApi<Professor[]>("/professors"),
      publicPresentationApi<Room[]>("/rooms"),
      publicPresentationApi<TimeSlot[]>("/timeslots"),
      publicPresentationApi<Campus[]>("/campuses")
    ])
      .then(([courses, professors, rooms, slots, campuses]) =>
        setCatalog({ courses, professors, rooms, slots, campuses })
      )
      .catch(console.error);
  }, []);

  if (running) {
    return (
      <section className="grid place-items-center gap-5 text-center">
        <div className="relative grid h-40 w-40 place-items-center rounded-full border border-lake/20 bg-white shadow-panel">
          <motion.div
            className="absolute inset-2 rounded-full border-4 border-lake border-t-transparent"
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
          />
          <Loader2 size={34} className="animate-spin text-lake" />
        </div>
        <div>
          <h2 className="text-4xl font-semibold">Otimização em execução</h2>
          <p className="mt-3 text-lg text-slate-700">
            Status: {run?.status ?? "aguardando"} · Tempo: {formatElapsed(elapsed)}
          </p>
          <p className="mt-2 text-sm text-slate-600">A busca é assíncrona e será atualizada automaticamente.</p>
          {optimizationError ? <p className="mt-2 text-sm text-rose">{optimizationError}</p> : null}
        </div>
      </section>
    );
  }

  const sectionPlans = plannedSectionsFromMetrics(run.metrics);
  const hardDiagnostics = hardDiagnosticsFromMetrics(run.metrics);
  const rawUnplannedDemandRequests =
    metricNumber(run.metrics?.student_demand_plan?.unplanned_request_count) ??
    metricNumber(run.metrics?.student_demand_plan?.unplanned_choice_groups);
  const unplannedAfterEnrollment = run.metrics?.enrollment_round?.unplanned_after_enrollment;
  const finalUnplannedDemandRequests = metricNumber(unplannedAfterEnrollment?.remaining);
  const unplannedDemandRequests = finalUnplannedDemandRequests ?? rawUnplannedDemandRequests;
  const enrolledUnplannedDemandRequests = metricNumber(unplannedAfterEnrollment?.enrolled);
  const sectionsBelowMinimum = sectionPlans.filter(
    (section) => section.planned_students > 0 && section.planned_students < 3
  ).length;
  const unservedSectionDemand = sectionPlans.reduce(
    (total, section) => total + Math.max(0, section.planned_unserved_demand ?? 0),
    0
  );
  const sectionIssues = sectionPlans.filter(
    (section) =>
      (section.planned_students > 0 && section.planned_students < 3) ||
      (section.planned_unserved_demand ?? 0) > 0
  );
  const displayStatus = run.metrics?.optimization_status ?? run.status;

  return (
    <section className="grid gap-5 pb-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <MetricTile label="Status" value={displayStatus} tone={displayStatus === "feasible" ? "green" : "amber"} />
        <MetricTile label="Tempo total" value={formatMs(Number(run.metrics?.elapsed_ms ?? 0))} />
        <MetricTile
          label="Conflitos hard"
          value={String(run.metrics?.hard_conflicts ?? "-")}
          tone={(run.metrics?.hard_conflicts ?? 0) > 0 ? "amber" : "green"}
        />
        <MetricTile label="Alocados" value={String(run.metrics?.enrollment_round?.enrolled ?? "-")} tone="green" />
        <MetricTile label="Turmas abertas" value={String(sectionPlans.length || "-")} />
        <MetricTile label="Alternativas usadas" value={String(run.metrics?.student_demand_plan?.alternative_assignments ?? "-")} />
        <MetricTile
          label="Demandas pendentes"
          value={String(unplannedDemandRequests ?? "-")}
          tone={unplannedDemandRequests ? "amber" : "green"}
        />
        <MetricTile label="Turmas abaixo do mínimo" value={String(sectionsBelowMinimum)} tone={sectionsBelowMinimum ? "amber" : "green"} />
        <MetricTile label="Sobras sem turma" value={String(unservedSectionDemand)} tone={unservedSectionDemand ? "amber" : "green"} />
      </div>
      <ResultDiagnostics
        hardDiagnostics={hardDiagnostics}
        sectionIssues={sectionIssues}
        unplannedDemandRequests={unplannedDemandRequests ?? 0}
        rawUnplannedDemandRequests={rawUnplannedDemandRequests ?? 0}
        enrolledUnplannedDemandRequests={enrolledUnplannedDemandRequests ?? 0}
      />
      <CalendarPreview
        assignments={assignments}
        assignmentDetails={assignmentDetails}
        catalog={catalog}
        sectionPlans={sectionPlans}
      />
    </section>
  );
}

function FinalSlide() {
  return (
    <NarrativeSlide
      icon={School}
      title="A contribuição central foi traduzir escala de tripulação para escala acadêmica"
      lead="O estudo da Air New Zealand mostrou que separar o problema, formalizar regras e negociar soft constraints torna a otimização aplicável no mundo real."
      points={[
        "No OptiGrade, tours-of-duty viram ofertas de cadeiras; rostering vira alocação docente e matrícula.",
        "A Pesquisa Operacional fornece a linguagem para distinguir restrições obrigatórias, preferências e custo de decisão.",
        "O MVP acrescenta a tecnologia atual: web, autenticação, QR temporário, execução assíncrona, múltiplos algoritmos e participação direta dos usuários."
      ]}
    />
  );
}

function TwoColumn({
  visual,
  eyebrow,
  title,
  body,
  stats,
  link
}: {
  visual: React.ReactNode;
  eyebrow: string;
  title: string;
  body: string;
  stats: [string, string][];
  link?: string;
}) {
  return (
    <section className="grid max-h-full items-center gap-5 lg:grid-cols-[1fr_0.85fr]">
      <div>
        <p className="text-sm font-semibold uppercase text-lake">{eyebrow}</p>
        <h2 className="mt-3 max-w-4xl text-3xl font-semibold leading-tight sm:text-5xl">{title}</h2>
        <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-700">{body}</p>
        {link ? (
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="focus-ring mt-5 inline-flex h-11 items-center gap-2 rounded-md border border-slateLine bg-white px-4 text-sm font-semibold transition hover:-translate-y-0.5 hover:border-lake hover:text-lake"
          >
            <Github size={17} /> GitHub público MIT <ExternalLink size={15} />
          </a>
        ) : null}
        <div className="mt-5 grid gap-2 sm:grid-cols-3">
          {stats.map(([label, value]) => (
            <MetricTile key={label} label={label} value={value} />
          ))}
        </div>
      </div>
      <Panel className="h-[260px] overflow-hidden p-0 sm:h-[360px] lg:h-[430px]">{visual}</Panel>
    </section>
  );
}

function NarrativeSlide({
  icon: Icon,
  title,
  lead,
  points
}: {
  icon: typeof BookOpen;
  title: string;
  lead: string;
  points: string[];
}) {
  return (
    <section className="grid max-h-full gap-4 lg:grid-cols-[0.82fr_1fr]">
      <Panel className="grid content-between gap-5">
        <Icon size={42} className="text-lake" />
        <div>
          <h2 className="text-3xl font-semibold leading-tight sm:text-5xl">{title}</h2>
          <p className="mt-4 text-base leading-relaxed text-slate-700">{lead}</p>
        </div>
      </Panel>
      <div className="grid content-center gap-3">
        {points.map((point, index) => (
          <motion.div
            key={point}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.08 }}
            className="rounded-md border border-slateLine bg-white px-4 py-4 text-sm leading-relaxed shadow-panel"
          >
            {point}
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function QrSlide({
  title,
  subtitle,
  link,
  video,
  onNext
}: {
  title: string;
  subtitle: string;
  link?: string;
  video: string;
  onNext: () => void;
}) {
  return (
    <section className="grid max-h-full items-center gap-4 lg:grid-cols-[340px_1fr]">
      <Panel className="grid justify-items-center gap-3 text-center">
        <h2 className="text-2xl font-semibold">{title}</h2>
        <p className="text-sm leading-relaxed text-slate-600">{subtitle}</p>
        <div className="grid h-52 w-52 place-items-center rounded-md border border-slateLine bg-white sm:h-60 sm:w-60">
          {link ? <QRCodeSVG value={link} size={200} /> : <Loader2 className="animate-spin text-lake" />}
        </div>
        {link ? <p className="break-all text-xs text-slate-500">{link}</p> : null}
        <button
          type="button"
          data-slide-primary
          onClick={onNext}
          className="focus-ring inline-flex h-11 items-center gap-2 rounded-md bg-lake px-5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#155876]"
        >
          Professor/alunos finalizaram <ArrowRight size={17} />
        </button>
      </Panel>
      <Panel className="overflow-hidden p-0">
        <video src={video} controls autoPlay muted loop playsInline className="aspect-video w-full bg-ink object-cover" />
      </Panel>
    </section>
  );
}

function ImpactPanel() {
  return (
    <Panel className="grid gap-4">
      <h3 className="text-xl font-semibold">Impactos relatados</h3>
      {[
        ["NZ$ 15,655 mi/ano", "economia conservadora anual"],
        ["NZ$ 2 mi", "custo de desenvolvimento em 15 anos"],
        ["11%", "do lucro operacional líquido de 1999"],
        ["27 → 15", "pessoas necessárias para resolver o problema"]
      ].map(([value, label]) => (
        <div key={value} className="rounded-md border border-slateLine bg-slate-50 px-4 py-3">
          <div className="text-2xl font-semibold text-lake">{value}</div>
          <div className="text-sm text-slate-600">{label}</div>
        </div>
      ))}
    </Panel>
  );
}

function ComparisonColumn({ title, items }: { title: string; items: string[] }) {
  return (
    <Panel>
      <h2 className="text-3xl font-semibold">{title}</h2>
      <div className="mt-5 grid gap-3">
        {items.map((item) => (
          <div key={item} className="rounded-md border border-slateLine bg-slate-50 px-4 py-3 text-sm leading-relaxed">
            {item}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function StatFromApi({
  label,
  value,
  icon: Icon,
  suffix = "",
  warning = false
}: {
  label: string;
  value?: number;
  icon: typeof Cpu;
  suffix?: string;
  warning?: boolean;
}) {
  return (
    <Panel className={`p-3 ${warning ? "border-amber/40 bg-amber/10" : ""}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600">{label}</span>
        <Icon size={18} className={warning ? "text-amber" : "text-lake"} />
      </div>
      <div className="mt-2 text-2xl font-semibold">
        {typeof value === "number" ? `${formatStatNumber(value)}${suffix}` : "-"}
      </div>
    </Panel>
  );
}

function MetricTile({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "green" | "amber" }) {
  const toneClass = tone === "green" ? "text-moss" : tone === "amber" ? "text-amber" : "text-ink";
  return (
    <div className="rounded-md border border-slateLine bg-white px-4 py-4 shadow-panel transition hover:-translate-y-0.5">
      <div className={`text-2xl font-semibold ${toneClass}`}>{value}</div>
      <div className="mt-1 text-sm text-slate-600">{label}</div>
    </div>
  );
}

function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-slateLine bg-white/90 p-5 shadow-panel backdrop-blur ${className}`}>{children}</section>;
}

type CalendarCatalog = {
  courses: Course[];
  professors: Professor[];
  rooms: Room[];
  slots: TimeSlot[];
  campuses: Campus[];
};

type PlannedSection = {
  course_name?: string;
  db_course_id: string;
  section_index: number;
  section_label: string;
  source_course_ids?: string[];
  degree_programs?: string[];
  campuses?: string[];
  context_key?: string | null;
  workload_hours?: number;
  theoretical_hours?: number;
  practical_hours?: number;
  course_turns?: string[];
  regular_time_windows?: Array<{
    start_minute: number;
    end_minute: number;
    turn?: string;
  }>;
  planned_students: number;
  planned_capacity_target?: number;
  planned_total_demand?: number;
  planned_unserved_demand?: number;
  strategy?: string;
};

type HardDiagnostic = {
  code?: string;
  message?: string;
  course_id?: string;
  assignment?: string;
  session_index?: number;
  [key: string]: unknown;
};

function ResultDiagnostics({
  hardDiagnostics,
  sectionIssues,
  unplannedDemandRequests,
  rawUnplannedDemandRequests,
  enrolledUnplannedDemandRequests
}: {
  hardDiagnostics: HardDiagnostic[];
  sectionIssues: PlannedSection[];
  unplannedDemandRequests: number;
  rawUnplannedDemandRequests: number;
  enrolledUnplannedDemandRequests: number;
}) {
  const hasProblems = hardDiagnostics.length > 0 || sectionIssues.length > 0 || unplannedDemandRequests > 0;
  if (!hasProblems) {
    return (
      <Panel className="border-moss/30 bg-moss/10">
        <div className="flex items-center gap-3">
          <CheckCircle2 size={22} className="text-moss" />
          <div>
            <h2 className="text-lg font-semibold">Sem pendências operacionais no resultado</h2>
            <p className="text-sm text-slate-700">
              A rodada não retornou conflitos hard, sobras de demanda ou turmas abaixo do mínimo planejado.
            </p>
            {rawUnplannedDemandRequests > 0 && enrolledUnplannedDemandRequests > 0 ? (
              <p className="mt-1 text-sm text-slate-700">
                {enrolledUnplannedDemandRequests} pedidos que ficaram fora do plano intermediário foram atendidos
                na matrícula final.
              </p>
            ) : null}
          </div>
        </div>
      </Panel>
    );
  }

  return (
    <Panel className="border-amber/40 bg-amber/10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <AlertTriangle size={22} className="mt-1 text-amber" />
          <div>
            <h2 className="text-lg font-semibold">Pendências para correção da rodada</h2>
            <p className="text-sm text-slate-700">
              “Demandas pendentes” considera apenas pedidos que seguiram sem matrícula depois da etapa final de
              alocação. “Turmas abaixo do mínimo” só conta turmas abertas com menos de 3 inscritos.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href="/app/planejamento"
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-slateLine bg-white px-3 text-sm font-semibold transition hover:-translate-y-0.5 hover:border-lake hover:text-lake"
          >
            Abrir planejamento <ExternalLink size={15} />
          </a>
          <a
            href="/app/cadastros/cadeiras"
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-slateLine bg-white px-3 text-sm font-semibold transition hover:-translate-y-0.5 hover:border-lake hover:text-lake"
          >
            Editar cadeiras <ExternalLink size={15} />
          </a>
        </div>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {hardDiagnostics.length ? (
          <div className="rounded-md border border-white/80 bg-white p-3">
            <h3 className="text-sm font-semibold uppercase text-slate-600">Conflitos hard</h3>
            <div className="mt-2 grid max-h-64 gap-2 overflow-auto pr-1">
              {hardDiagnostics.map((item, index) => (
                <div key={`${item.code ?? "diagnostic"}-${index}`} className="rounded-md border border-slateLine px-3 py-2 text-xs">
                  <div className="font-semibold text-ink">{item.message ?? item.code ?? "Restrição obrigatória"}</div>
                  <div className="mt-1 text-slate-600">
                    {item.code ? `Código: ${item.code}` : null}
                    {item.course_id ? ` · Curso: ${item.course_id}` : null}
                    {item.assignment ? ` · Oferta: ${item.assignment}` : null}
                    {typeof item.session_index === "number" ? ` · Sessão: ${item.session_index + 1}` : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {sectionIssues.length || unplannedDemandRequests > 0 ? (
          <div className="rounded-md border border-white/80 bg-white p-3">
            <h3 className="text-sm font-semibold uppercase text-slate-600">Demanda e turmas</h3>
            <div className="mt-2 grid gap-2 text-xs">
              {unplannedDemandRequests > 0 ? (
                <div className="rounded-md border border-slateLine px-3 py-2">
                  <div className="font-semibold text-ink">{unplannedDemandRequests} pedidos seguem sem atendimento</div>
                  <div className="mt-1 text-slate-600">
                    Esses são casos que não foram resolvidos pela combinação entre plano de ofertas, alternativas
                    informadas e rodada final de matrícula.
                  </div>
                </div>
              ) : null}
              {sectionIssues.map((section) => (
                <div key={`${section.db_course_id}-${section.section_index}`} className="rounded-md border border-slateLine px-3 py-2">
                  <div className="font-semibold text-ink">{section.section_label}</div>
                  <div className="mt-1 text-slate-600">
                    {section.planned_students} inscritos planejados
                    {section.planned_unserved_demand ? ` · ${section.planned_unserved_demand} sem turma` : ""}
                    {section.strategy ? ` · ${section.strategy}` : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function CalendarPreview({
  assignments,
  assignmentDetails,
  catalog,
  sectionPlans
}: {
  assignments: Assignment[];
  assignmentDetails: AssignmentDetail[];
  catalog: CalendarCatalog | null;
  sectionPlans: PlannedSection[];
}) {
  const [selectedDetail, setSelectedDetail] = useState<AssignmentDetail | null>(null);
  const courseById = useMemo(() => indexBy(catalog?.courses ?? []), [catalog?.courses]);
  const professorById = useMemo(() => indexBy(catalog?.professors ?? []), [catalog?.professors]);
  const roomById = useMemo(() => indexBy(catalog?.rooms ?? []), [catalog?.rooms]);
  const campusById = useMemo(() => indexBy(catalog?.campuses ?? []), [catalog?.campuses]);
  const detailByAssignmentId = useMemo(
    () => indexBy(assignmentDetails.map((detail) => ({ ...detail, id: detail.assignment.id }))),
    [assignmentDetails]
  );
  const sectionByKey = useMemo(
    () =>
      Object.fromEntries(
        sectionPlans.map((section) => [`${section.db_course_id}:${section.section_index}`, section])
      ) as Record<string, PlannedSection>,
    [sectionPlans]
  );
  const slots = [...(catalog?.slots ?? [])].sort((a, b) => a.day - b.day || a.start_minute - b.start_minute);
  const usedSlotIds = new Set(assignments.map((assignment) => assignment.time_slot_id));
  const visibleSlots = slots.filter((slot) => usedSlotIds.has(slot.id));
  const visibleAssignmentCount = visibleSlots.reduce(
    (total, slot) => total + assignments.filter((assignment) => assignment.time_slot_id === slot.id).length,
    0
  );
  return (
    <Panel className="overflow-hidden p-0">
      <div className="border-b border-slateLine px-5 py-4">
        <h2 className="text-xl font-semibold">Calendário final de ofertas</h2>
        <p className="text-sm text-slate-600">
          Visão compacta das primeiras ofertas alocadas. Total: {assignments.length} sessões.
        </p>
      </div>
      <div className="grid gap-2 p-4 md:grid-cols-2 xl:grid-cols-4">
        {visibleSlots.map((slot) => {
          const cellAssignments = assignments.filter((assignment) => assignment.time_slot_id === slot.id);
          return (
            <div key={slot.id} className="min-h-28 rounded-md border border-slateLine bg-slate-50 p-3">
              <div className="text-xs font-semibold uppercase text-slate-500">
                {dayLabels[slot.day]} · {minutesToLabel(slot.start_minute)}-{minutesToLabel(slot.end_minute)}
                {" · "}
                {turnLabel(turnKeyForWindow(slot.start_minute, slot.end_minute))}
              </div>
              <div className="mt-2 grid gap-2">
                {cellAssignments.length ? (
                  cellAssignments.map((assignment) => {
                    const course = courseById[assignment.course_id];
                    const professor = professorById[assignment.professor_id];
                    const room = roomById[assignment.room_id];
                    const campus = campusById[room?.campus_id ?? ""];
                    const sectionIndex = Math.floor((assignment.session_index ?? 0) / 100);
                    const sectionPlan = sectionByKey[`${assignment.course_id}:${sectionIndex}`];
                    const courseTitle = sectionPlan?.course_name ?? course?.name ?? assignment.course_id;
                    const coursePeriod = sectionPlan ? coursePeriodLabel(sectionPlan) : null;
                    const workload = sectionPlan?.workload_hours ?? course?.workload_hours;
                    const detail = detailByAssignmentId[assignment.id];
                    const enrolledCount = detail?.enrollments.length ?? sectionPlan?.planned_students ?? 0;
                    return (
                      <button
                        key={assignment.id}
                        type="button"
                        onClick={() => detail && setSelectedDetail(detail)}
                        disabled={!detail}
                        className="focus-ring group rounded-md border border-lake/20 bg-white px-3 py-2 text-left text-[11px] transition hover:-translate-y-0.5 hover:border-lake hover:shadow-panel disabled:cursor-default disabled:hover:translate-y-0 disabled:hover:border-lake/20 disabled:hover:shadow-none"
                      >
                        <div className="font-semibold text-ink">{courseTitle}</div>
                        <div className="mt-1 font-medium text-lake">
                          {sectionPlan
                            ? `${sectionPlan.section_label} · ${enrolledCount} inscritos`
                            : `Turma ${sectionIndex + 1}`}
                        </div>
                        <div className="mt-1 text-slate-600">
                          Turno do curso: {coursePeriod ?? "não informado"}
                          {workload ? ` · ${workload}h` : ""}
                        </div>
                        <div className="text-slate-600">
                          Oferta: {dayLabels[slot.day]} · {turnLabel(turnKeyForWindow(slot.start_minute, slot.end_minute))}
                          {" · "}
                          {minutesToLabel(slot.start_minute)}-{minutesToLabel(slot.end_minute)}
                        </div>
                        <div className="mt-1 text-slate-600">{professor?.name ?? assignment.professor_id}</div>
                        <div className="text-slate-600">
                          {room?.name ?? assignment.room_id}
                          {room ? ` · ${room.capacity} vagas físicas` : ""}
                          {campus ? ` · ${campus.name}` : ""}
                        </div>
                        <div className="mt-2 inline-flex items-center gap-1 font-semibold text-lake opacity-80 transition group-hover:opacity-100">
                          <Info size={12} /> Ver detalhes
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="rounded-md border border-dashed border-slateLine px-3 py-6 text-center text-xs text-slate-500">
                    Sem oferta neste horário
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {assignments.length > visibleAssignmentCount ? (
          <div className="grid min-h-28 place-items-center rounded-md border border-dashed border-lake/30 bg-white p-3 text-center text-sm font-semibold text-lake">
            +{assignments.length - visibleAssignmentCount} sessões na grade completa
          </div>
        ) : null}
      </div>
      <AssignmentDetailModal detail={selectedDetail} onClose={() => setSelectedDetail(null)} />
    </Panel>
  );
}

function AssignmentDetailModal({
  detail,
  onClose
}: {
  detail: AssignmentDetail | null;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState("inscricoes");

  useEffect(() => {
    if (detail) setActiveTab("inscricoes");
  }, [detail?.assignment.id, detail]);

  useEffect(() => {
    if (!detail) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [detail, onClose]);

  if (!detail) return null;

  const tabItems = [
    { id: "inscricoes", label: "Inscrições", icon: ClipboardList },
    { id: "turma", label: "Turma", icon: CalendarDays },
    { id: "professor", label: "Professor", icon: UserRoundCog },
    { id: "solver", label: "Solver", icon: Cpu }
  ];
  const courseName = detail.section?.course_name ?? detail.course?.name ?? detail.assignment.course_id;
  const slot = detail.slot;
  const room = detail.room;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 grid place-items-center bg-ink/45 p-3 backdrop-blur-sm sm:p-5"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label={`Detalhes de ${courseName}`}
          initial={{ opacity: 0, y: 18, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 12, scale: 0.98 }}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          className="grid max-h-[92vh] min-w-0 w-full max-w-5xl grid-cols-[minmax(0,1fr)] grid-rows-[auto_auto_1fr] overflow-hidden rounded-lg border border-slateLine bg-white shadow-2xl"
        >
          <div className="flex items-start justify-between gap-3 border-b border-slateLine px-4 py-4 sm:px-5">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-lake">Detalhe da oferta</p>
              <h2 className="mt-1 truncate text-xl font-semibold sm:text-2xl">{courseName}</h2>
              <p className="mt-1 text-sm text-slate-600">
                {detail.section?.section_label ?? `Turma ${(detail.assignment.section_index ?? 0) + 1}`}
                {slot ? ` · ${dayLabels[slot.day]} ${minutesToLabel(slot.start_minute)}-${minutesToLabel(slot.end_minute)}` : ""}
                {room ? ` · ${room.name}` : ""}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="focus-ring grid h-10 w-10 shrink-0 place-items-center rounded-md border border-slateLine bg-white transition hover:-translate-y-0.5 hover:border-lake hover:text-lake"
              aria-label="Fechar detalhes"
            >
              <X size={18} />
            </button>
          </div>

          <div className="min-w-0 w-full max-w-full overflow-hidden border-b border-slateLine bg-slate-50 px-3 py-2">
            <div className="flex min-w-0 w-full max-w-full gap-2 overflow-x-auto pb-1 [scrollbar-gutter:stable]">
              {tabItems.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`focus-ring inline-flex h-10 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-semibold transition ${
                    activeTab === tab.id
                      ? "border-lake bg-white text-lake shadow-panel"
                      : "border-transparent bg-transparent text-slate-600 hover:bg-white hover:text-ink"
                  }`}
                >
                  <tab.icon size={16} />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="min-w-0 overflow-y-auto p-4 sm:p-5">
            {activeTab === "inscricoes" ? <EnrollmentTab detail={detail} /> : null}
            {activeTab === "turma" ? <ClassTab detail={detail} /> : null}
            {activeTab === "professor" ? <ProfessorTab detail={detail} /> : null}
            {activeTab === "solver" ? <SolverTab detail={detail} /> : null}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function EnrollmentTab({ detail }: { detail: AssignmentDetail }) {
  const enrollments = detail.enrollments;
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricTile label="Inscritos vinculados" value={String(enrollments.length)} tone={enrollments.length ? "green" : "amber"} />
        <MetricTile label="Capacidade física" value={String(detail.room?.capacity ?? "-")} />
        <MetricTile label="Demanda planejada" value={String(detail.section?.planned_students ?? "-")} />
      </div>
      {enrollments.length ? (
        <div className="grid gap-3">
          {enrollments.map((enrollment) => (
            <EnrollmentDetailCard key={enrollment.id} enrollment={enrollment} />
          ))}
        </div>
      ) : (
        <DetailBlock title="Sem inscrições atribuídas">
          <p className="text-sm leading-relaxed text-slate-700">
            A oferta existe, mas o detalhe público do run não encontrou alunos matriculados nesta turma.
          </p>
        </DetailBlock>
      )}
    </div>
  );
}

function EnrollmentDetailCard({ enrollment }: { enrollment: AssignmentEnrollmentDetail }) {
  const request = enrollment.request;
  return (
    <div className="rounded-md border border-slateLine bg-slate-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{enrollment.student.name}</h3>
          <p className="mt-1 text-sm text-slate-600">
            {enrollment.student.degree_program_name ?? "Curso de origem não informado"}
            {enrollment.student.current_semester ? ` · ${enrollment.student.current_semester}º semestre` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Tag>{enrollment.decision_type}</Tag>
          <Tag>{enrollment.status}</Tag>
          <Tag>{enrollment.score.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} pts</Tag>
        </div>
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <DetailBlock title="Origem da escolha">
          <DetailKeyValue label="Cadeira solicitada" value={enrollment.requested_course?.name ?? "-"} />
          <DetailKeyValue label="Cadeira ofertada" value={enrollment.assigned_course?.name ?? "-"} />
          <DetailKeyValue label="Posição na fila" value={request ? String(request.preference_order) : "-"} />
          <DetailKeyValue label="Prioridade" value={request ? String(request.priority) : "-"} />
          <DetailKeyValue label="Grupo de alternativa" value={request?.alternative_group ?? "-"} />
          {request?.desired_day !== null && request?.desired_day !== undefined ? (
            <DetailKeyValue
              label="Janela desejada"
              value={`${dayLabels[request.desired_day]} ${formatOptionalWindow(request.desired_start_minute, request.desired_end_minute)}`}
            />
          ) : null}
        </DetailBlock>
        <DetailBlock title="Por que caiu nesta turma">
          <ReasonList items={enrollment.why_this_section} />
        </DetailBlock>
      </div>
      <div className="mt-3">
        <DetailBlock title="Pontuação da vaga">
          <ScoreBreakdown values={enrollment.score_breakdown} />
        </DetailBlock>
      </div>
    </div>
  );
}

function ClassTab({ detail }: { detail: AssignmentDetail }) {
  const slot = detail.slot;
  const coursePeriod = detail.section ? coursePeriodLabel(detail.section as PlannedSection) : detail.course?.official_period;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <DetailBlock title="Oferta">
        <DetailKeyValue label="Cadeira" value={detail.section?.course_name ?? detail.course?.name ?? "-"} />
        <DetailKeyValue label="Código" value={detail.course?.code ?? "-"} />
        <DetailKeyValue label="Curso de origem" value={detail.course?.degree_program_name ?? "-"} />
        <DetailKeyValue label="Período do curso" value={coursePeriod ? turnLabel(coursePeriod) : "-"} />
        <DetailKeyValue label="Carga total" value={detail.course?.workload_hours ? `${detail.course.workload_hours}h` : "-"} />
        <DetailKeyValue label="Horas teóricas" value={detail.course?.theoretical_hours ? `${detail.course.theoretical_hours}h` : "-"} />
        <DetailKeyValue label="Contexto" value={detail.course?.context_key ?? "-"} />
        <DetailKeyValue label="Compartilhável" value={detail.course?.shareable ? "sim" : "não"} />
      </DetailBlock>
      <DetailBlock title="Sala e horário">
        <DetailKeyValue label="Horário" value={slot ? `${dayLabels[slot.day]} ${minutesToLabel(slot.start_minute)}-${minutesToLabel(slot.end_minute)}` : "-"} />
        <DetailKeyValue label="Turno da oferta" value={slot ? turnLabel(turnKeyForWindow(slot.start_minute, slot.end_minute)) : "-"} />
        <DetailKeyValue label="Sala" value={detail.room?.name ?? "-"} />
        <DetailKeyValue label="Campus" value={detail.room?.campus_name ?? detail.course?.campus_name ?? "-"} />
        <DetailKeyValue label="Capacidade" value={detail.room ? `${detail.room.capacity} vagas` : "-"} />
        <DetailKeyValue label="Tipo" value={detail.room?.kind === "lab" ? "laboratório" : "teórica"} />
      </DetailBlock>
      <DetailBlock title="Decisão da turma">
        <DetailKeyValue label="Turma" value={detail.section?.section_label ?? `Turma ${(detail.assignment.section_index ?? 0) + 1}`} />
        <DetailKeyValue label="Inscritos planejados" value={String(detail.section?.planned_students ?? detail.enrollments.length)} />
        <DetailKeyValue label="Estratégia" value={typeof detail.section?.strategy === "string" ? detail.section.strategy : "-"} />
        <DetailKeyValue label="Origem da alocação" value={detail.assignment.origin} />
      </DetailBlock>
      <DetailBlock title="Justificativa de sala e horário">
        <ReasonList items={detail.decision.why_time_room} />
      </DetailBlock>
    </div>
  );
}

function ProfessorTab({ detail }: { detail: AssignmentDetail }) {
  const professor = detail.professor;
  if (!professor) {
    return <DetailBlock title="Professor não encontrado">Dados docentes indisponíveis para esta oferta.</DetailBlock>;
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <DetailBlock title="Docente designado">
        <DetailKeyValue label="Nome" value={professor.name} />
        <DetailKeyValue label="Departamento" value={professor.department ?? "-"} />
        <DetailKeyValue label="E-mail" value={professor.email ?? "-"} />
        <DetailKeyValue label="Regime" value={professor.contract?.regime ?? "-"} />
        <DetailKeyValue label="Carga mínima" value={professor.contract ? `${professor.contract.min_hours}h` : "-"} />
        <DetailKeyValue label="Carga máxima" value={professor.contract ? `${professor.contract.max_hours}h` : "-"} />
        <DetailKeyValue label="Emprestado" value={professor.contract?.is_borrowed ? "sim" : "não"} />
      </DetailBlock>
      <DetailBlock title="Por que este professor">
        <ReasonList items={detail.decision.why_professor} />
      </DetailBlock>
      <DetailBlock title="Disponibilidade cadastrada">
        <div className="grid max-h-72 gap-2 overflow-y-auto pr-1">
          {professor.availability.length ? (
            professor.availability.map((item, index) => (
              <div
                key={`${item.day}-${item.start_minute}-${item.end_minute}-${index}`}
                className={`rounded-md border px-3 py-2 text-sm ${
                  item.matches_assignment ? "border-moss/40 bg-moss/10" : "border-slateLine bg-white"
                }`}
              >
                <div className="font-semibold">
                  {dayLabels[item.day]} {minutesToLabel(item.start_minute)}-{minutesToLabel(item.end_minute)}
                </div>
                <div className="text-xs text-slate-600">
                  {item.kind} · {item.strength} · {item.source}
                  {item.matches_assignment ? " · cobre esta oferta" : ""}
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-600">Nenhuma janela cadastrada.</p>
          )}
        </div>
      </DetailBlock>
      <DetailBlock title="Preferências e restrições">
        <div className="grid gap-3">
          {professor.course_preferences.length ? (
            professor.course_preferences.map((item, index) => (
              <div key={`${item.course_id}-${index}`} className="rounded-md border border-slateLine bg-white px-3 py-2 text-sm">
                Preferência {item.preference} · {item.strength}
                {item.note ? <div className="mt-1 text-xs text-slate-600">{item.note}</div> : null}
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-600">Sem preferência específica para esta cadeira.</p>
          )}
          {professor.constraints.length ? (
            professor.constraints.map((item, index) => (
              <div key={`${item.natural_language}-${index}`} className="rounded-md border border-slateLine bg-white px-3 py-2 text-sm">
                <div className="font-semibold">{item.strength}</div>
                <div className="mt-1 text-slate-700">{item.natural_language}</div>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-600">Sem restrição textual registrada.</p>
          )}
        </div>
      </DetailBlock>
    </div>
  );
}

function SolverTab({ detail }: { detail: AssignmentDetail }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <DetailBlock title="Decisão da alocação">
        <DetailKeyValue label="Origem" value={detail.decision.origin} />
        <DetailKeyValue label="Fixa/manual" value={detail.decision.fixed ? "sim" : "não"} />
        <DetailKeyValue label="Chave da seção" value={detail.decision.section_key} />
        <DetailKeyValue label="Sessão" value={String((detail.assignment.session_index ?? 0) % 100 + 1)} />
      </DetailBlock>
      <DetailBlock title="Violações">
        <DetailKeyValue label="Hard" value={String(detail.assignment.hard_violations.length)} />
        <DetailKeyValue label="Soft" value={String(detail.assignment.soft_violations.length)} />
        <JsonList values={detail.assignment.hard_violations} empty="Sem violação hard." />
        <JsonList values={detail.assignment.soft_violations} empty="Sem violação soft." />
      </DetailBlock>
      <DetailBlock title="Justificativas docentes">
        <ReasonList items={detail.decision.why_professor} />
      </DetailBlock>
      <DetailBlock title="Justificativas da turma">
        <ReasonList items={detail.decision.why_time_room} />
      </DetailBlock>
    </div>
  );
}

function DetailBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-slateLine bg-white p-3">
      <h3 className="text-sm font-semibold uppercase text-slate-600">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function DetailKeyValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 border-b border-slateLine/70 py-2 text-sm last:border-b-0">
      <div className="text-slate-500">{label}</div>
      <div className="min-w-0 font-medium text-ink">{value}</div>
    </div>
  );
}

function ReasonList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-sm text-slate-600">Sem justificativa registrada.</p>;
  return (
    <div className="grid gap-2">
      {items.map((item, index) => (
        <div key={`${item}-${index}`} className="rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-sm leading-relaxed text-slate-700">
          {item}
        </div>
      ))}
    </div>
  );
}

function ScoreBreakdown({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([, value]) => typeof value === "number" || typeof value === "string" || typeof value === "boolean");
  if (!entries.length) return <p className="text-sm text-slate-600">Pontuação detalhada indisponível.</p>;
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border border-slateLine bg-slate-50 px-3 py-2 text-sm">
          <div className="text-xs uppercase text-slate-500">{scoreLabel(key)}</div>
          <div className="mt-1 font-semibold">{String(value)}</div>
        </div>
      ))}
    </div>
  );
}

function JsonList({ values, empty }: { values: Array<Record<string, unknown>>; empty: string }) {
  if (!values.length) return <p className="mt-3 text-sm text-slate-600">{empty}</p>;
  return (
    <div className="mt-3 grid max-h-52 gap-2 overflow-y-auto pr-1">
      {values.map((item, index) => (
        <pre key={index} className="overflow-x-auto rounded-md border border-slateLine bg-slate-50 p-2 text-xs text-slate-700">
          {JSON.stringify(item, null, 2)}
        </pre>
      ))}
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex h-7 items-center rounded-md border border-lake/20 bg-lake/10 px-2 text-xs font-semibold text-lake">
      {children}
    </span>
  );
}

function formatOptionalWindow(start?: number | null, end?: number | null) {
  if (typeof start !== "number" || typeof end !== "number") return "horário livre";
  return `${minutesToLabel(start)}-${minutesToLabel(end)}`;
}

function scoreLabel(value: string) {
  const labels: Record<string, string> = {
    first_attempt: "primeira tentativa",
    regular: "regular",
    reoffer: "reoferta",
    semester_delay: "atraso",
    failed_grade_pressure: "pressão por reprovação",
    dependency_grade_average: "média nas dependências",
    dependency_grade_bonus: "bônus por dependências",
    student_priority: "prioridade do aluno",
    preference_order_penalty: "penalidade da fila"
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function plannedSectionsFromMetrics(metrics: OptimizationRun["metrics"] | null | undefined): PlannedSection[] {
  const plannedSections = metrics?.planned_sections;
  if (!Array.isArray(plannedSections)) return [];
  return plannedSections.filter(isPlannedSection);
}

function hardDiagnosticsFromMetrics(metrics: OptimizationRun["metrics"] | null | undefined): HardDiagnostic[] {
  const diagnostics = metrics?.hard_diagnostics;
  if (!Array.isArray(diagnostics)) return [];
  return diagnostics.filter(isHardDiagnostic).slice(0, 20);
}

function isPlannedSection(value: unknown): value is PlannedSection {
  if (!value || typeof value !== "object") return false;
  const section = value as Partial<PlannedSection>;
  return (
    typeof section.db_course_id === "string" &&
    typeof section.section_index === "number" &&
    typeof section.section_label === "string" &&
    typeof section.planned_students === "number"
  );
}

function isHardDiagnostic(value: unknown): value is HardDiagnostic {
  if (!value || typeof value !== "object") return false;
  const diagnostic = value as Partial<HardDiagnostic>;
  return (
    typeof diagnostic.code === "string" ||
    typeof diagnostic.message === "string" ||
    typeof diagnostic.course_id === "string" ||
    typeof diagnostic.assignment === "string"
  );
}

function metricNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function coursePeriodLabel(section: PlannedSection) {
  const directTurns = section.course_turns?.filter(Boolean) ?? [];
  const windowTurns = section.regular_time_windows?.map((window) => window.turn ?? turnKeyForWindow(window.start_minute, window.end_minute)) ?? [];
  const labels = Array.from(new Set([...directTurns, ...windowTurns].map(turnLabel))).filter(Boolean);
  if (!labels.length) return null;
  return labels.join(" / ");
}

function turnKeyForWindow(startMinute: number, endMinute: number) {
  if (startMinute >= 18 * 60) return "noturno";
  if (endMinute > 19 * 60) return startMinute >= 12 * 60 ? "tarde-noite" : "integral";
  if (endMinute <= 13 * 60) return "manha";
  if (startMinute >= 12 * 60) return "tarde";
  return "manha-tarde";
}

function turnLabel(value: string) {
  const labels: Record<string, string> = {
    manha: "manhã",
    tarde: "tarde",
    noturno: "noturno",
    "manha-tarde": "manhã e tarde",
    "tarde-noite": "tarde e noite",
    integral: "integral"
  };
  return labels[value] ?? value;
}

function indexBy<T extends { id: string }>(items: T[]) {
  return Object.fromEntries(items.map((item) => [item.id, item])) as Record<string, T>;
}

function formatMs(value: number) {
  if (!value) return "-";
  return formatElapsed(Math.round(value / 1000));
}

function formatStatNumber(value: number) {
  return Number.isInteger(value) ? value.toLocaleString("pt-BR") : value.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}
