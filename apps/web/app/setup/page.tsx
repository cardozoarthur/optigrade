import Link from "next/link";
import { SetupForm } from "@/components/auth/auth-forms";
import { bootstrapAdminExists } from "@/lib/auth/bootstrap";

export const dynamic = "force-dynamic";

export default async function SetupPage() {
  if (await bootstrapAdminExists()) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#eef3f7] px-4 py-8">
        <section className="w-full max-w-md rounded-lg border border-slateLine bg-white p-5 shadow-panel">
          <p className="text-xs font-semibold uppercase tracking-normal text-lake">Bootstrap indisponivel</p>
          <h1 className="mt-2 text-xl font-semibold">Administrador ja configurado</h1>
          <p className="mt-2 text-sm text-slate-600">
            O primeiro acesso ja foi concluido. Novos usuarios devem entrar por convite da organizacao.
          </p>
          <Link
            className="focus-ring mt-5 inline-flex h-10 items-center justify-center rounded-md bg-ink px-4 text-sm font-semibold text-white transition hover:bg-lake"
            href="/sign-in"
          >
            Ir para login
          </Link>
        </section>
      </main>
    );
  }

  return <SetupForm />;
}
