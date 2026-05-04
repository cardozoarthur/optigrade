import { redirect } from "next/navigation";
import { defaultPathForRole } from "@/lib/auth/permissions";
import { requireAcademicSession } from "@/lib/auth/session";

export default async function AppIndex() {
  const session = await requireAcademicSession();
  redirect(defaultPathForRole(session.role));
}
