import { redirect } from "next/navigation";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function TrabalhoIndex() {
  await requireAcademicSession("presentation:manage");
  redirect("/trabalho/apresentacao");
}
