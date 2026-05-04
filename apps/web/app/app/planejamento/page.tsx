import { BarChart3 } from "lucide-react";
import PlanningDashboard from "@/components/planning/planning-dashboard";
import { PageHeader } from "@/components/shell/page-header";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function PlanejamentoPage() {
  await requireAcademicSession("optimization:read");

  return (
    <>
      <PageHeader
        icon={BarChart3}
        title="Planejamento semestral"
        subtitle="Oferta, alocacao docente, salas, demanda discente e simulacao operacional"
      />
      <PlanningDashboard embedded />
    </>
  );
}
