import Link from "next/link";
import {
  BookOpen,
  CalendarClock,
  DoorOpen,
  GraduationCap,
  MapPinned,
  UserRoundCog,
  Workflow
} from "lucide-react";
import type { Route } from "next";
import { PageHeader } from "@/components/shell/page-header";
import { requireAcademicSession } from "@/lib/auth/session";

const resources = [
  { href: "/app/cadastros/campus", label: "Campi", description: "Unidades fisicas e cidades.", icon: MapPinned },
  { href: "/app/cadastros/cursos", label: "Cursos", description: "Cursos, departamentos e horarios regulares.", icon: GraduationCap },
  { href: "/app/cadastros/cadeiras", label: "Cadeiras", description: "Catalogo, contexto, demanda e carga horaria.", icon: BookOpen },
  { href: "/app/cadastros/restricoes", label: "Restricoes", description: "Pre-requisitos e co-requisitos multiplos.", icon: Workflow },
  { href: "/app/cadastros/alunos", label: "Alunos", description: "Vinculo ao curso e semestre atual.", icon: GraduationCap },
  { href: "/app/cadastros/professores", label: "Professores", description: "Carga, docentes emprestados e contrato.", icon: UserRoundCog },
  { href: "/app/cadastros/salas", label: "Salas", description: "Capacidade e tipo de ambiente.", icon: DoorOpen },
  { href: "/app/cadastros/horarios", label: "Horarios", description: "Slots base para geracao de grade.", icon: CalendarClock }
] as const;

export default async function ResourcesIndexPage() {
  await requireAcademicSession("catalog:read");

  return (
    <>
      <PageHeader
        icon={BookOpen}
        title="Cadastros"
        subtitle="Recursos editaveis usados pela otimizacao e pelos portais academicos"
      />
      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-5 md:px-5">
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {resources.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href as Route}
                className="focus-ring group rounded-lg border border-slateLine bg-white p-4 shadow-panel transition duration-150 hover:-translate-y-0.5 hover:border-lake"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-lake/10 text-lake">
                    <Icon size={18} />
                  </div>
                  <span className="text-xs font-semibold uppercase text-slate-500">Abrir</span>
                </div>
                <h2 className="mt-4 text-base font-semibold">{item.label}</h2>
                <p className="mt-1 text-sm text-slate-600">{item.description}</p>
              </Link>
            );
          })}
        </section>
      </div>
    </>
  );
}
