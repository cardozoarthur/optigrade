import { Suspense } from "react";
import { InvitationForm } from "@/components/auth/auth-forms";

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-slate-600">Carregando convite</main>}>
      <InvitationForm />
    </Suspense>
  );
}
