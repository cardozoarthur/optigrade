import { GraduationCap } from "lucide-react";
import { StudentWorkbench } from "@/components/planning/student-workbench";
import { PageHeader } from "@/components/shell/page-header";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function StudentPage() {
  const session = await requireAcademicSession("students:self");

  return (
    <>
      <PageHeader
        icon={GraduationCap}
        title="Escolha de cadeiras"
        subtitle="Sugestoes a partir do curso, historico concluido, pre-requisitos e demanda do proximo semestre"
      />
      <StudentWorkbench
        studentId={session.user.studentId}
        studentEmail={session.role === "student" ? session.user.email : null}
      />
    </>
  );
}
