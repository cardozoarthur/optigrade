import { DegreeProgramsPage } from "@/components/resources/resource-pages";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function Page() {
  await requireAcademicSession("catalog:write");
  return <DegreeProgramsPage />;
}
