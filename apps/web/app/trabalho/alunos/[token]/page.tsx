import { StudentPresentationClient } from "@/components/trabalho/student-presentation-client";

export default async function TrabalhoAlunoTokenPage({
  params
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <StudentPresentationClient token={token} />;
}
