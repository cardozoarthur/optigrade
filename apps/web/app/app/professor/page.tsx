import { UserRoundCog } from "lucide-react";
import { ProfessorWorkbench } from "@/components/planning/professor-workbench";
import { PageHeader } from "@/components/shell/page-header";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function ProfessorPage() {
  const session = await requireAcademicSession("faculty:read");

  return (
    <>
      <PageHeader
        icon={UserRoundCog}
        title="Area do professor"
        subtitle="Restricoes de disponibilidade, carga, preferencias de cadeira e regras complexas"
      />
      <ProfessorWorkbench professorId={session.user.professorId} />
    </>
  );
}
