"use client";

import React, { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Check, KeyRound, Loader2, LogIn, School, Send, ShieldCheck, UserPlus } from "lucide-react";
import { Field, PrimaryButton, inputClass } from "@/components/ui";

type Mode = "signin" | "signup";

export function SignInForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authFetch("/api/auth/sign-in/email", { email, password });
      router.push("/app");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSurface
      eyebrow="Acesso institucional"
      title="Entrar no OptiGrade"
      subtitle="Use uma conta convidada pela coordenacao, chefia, pro-reitoria ou administracao do piloto."
      error={error}
    >
      <form onSubmit={submit} className="grid gap-3">
        <Field label="E-mail">
          <input className={inputClass} value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
        </Field>
        <Field label="Senha">
          <input
            className={inputClass}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            required
          />
        </Field>
        <PrimaryButton type="submit" disabled={busy}>
          <span className="inline-flex items-center gap-2">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
            Entrar
          </span>
        </PrimaryButton>
      </form>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <Link className="font-semibold text-lake transition hover:text-ink" href="/setup">
          Preparar primeiro acesso
        </Link>
        <span className="text-slate-400">·</span>
        <Link className="font-semibold text-lake transition hover:text-ink" href="/accept-invitation">
          Aceitar convite
        </Link>
      </div>
    </AuthSurface>
  );
}

export function SetupForm() {
  const router = useRouter();
  const [name, setName] = useState("Administrador OptiGrade");
  const [email, setEmail] = useState("admin@ufpel.edu.br");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("UFPel - Piloto OptiGrade");
  const [slug, setSlug] = useState("ufpel-piloto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authFetch("/api/bootstrap", {
        name,
        email,
        password,
        organizationName,
        slug,
      });
      router.push("/sign-in");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSurface
      eyebrow="Bootstrap do piloto"
      title="Criar organizacao e administrador"
      subtitle="Este formulario cria a primeira unidade academica no Better Auth Organization e ativa a sessao por cookie."
      error={error}
    >
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nome do administrador">
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} required />
        </Field>
        <Field label="E-mail">
          <input className={inputClass} value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
        </Field>
        <Field label="Senha">
          <input
            className={inputClass}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            required
          />
        </Field>
        <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
          <Field label="Organizacao">
            <input
              className={inputClass}
              value={organizationName}
              onChange={(event) => setOrganizationName(event.target.value)}
              required
            />
          </Field>
          <Field label="Slug">
            <input className={inputClass} value={slug} onChange={(event) => setSlug(event.target.value)} required />
          </Field>
        </div>
        <PrimaryButton type="submit" disabled={busy}>
          <span className="inline-flex items-center gap-2">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
            Criar acesso
          </span>
        </PrimaryButton>
      </form>
    </AuthSurface>
  );
}

export function InvitationForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const invitationId = searchParams.get("id") ?? "";
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actionLabel = useMemo(() => (mode === "signin" ? "Entrar e aceitar" : "Criar senha e aceitar"), [mode]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signup") {
        await authFetch("/api/auth/sign-up/email", { name: name || email, email, password });
      } else {
        await authFetch("/api/auth/sign-in/email", { email, password });
      }
      await authFetch("/api/auth/organization/accept-invitation", { invitationId });
      setAccepted(true);
      setTimeout(() => {
        router.push("/app");
        router.refresh();
      }, 450);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSurface
      eyebrow="Convite de organizacao"
      title="Aceitar convite"
      subtitle="Entre com a conta convidada ou crie a primeira senha para concluir o vinculo com a unidade academica."
      error={error}
    >
      <div className="mb-4 grid grid-cols-2 rounded-md border border-slateLine bg-slate-50 p-1">
        {(["signin", "signup"] as const).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setMode(item)}
            className={`h-9 rounded text-sm font-semibold transition ${
              mode === item ? "bg-white text-ink shadow-panel" : "text-slate-600 hover:text-ink"
            }`}
          >
            {item === "signin" ? "Ja tenho conta" : "Criar conta"}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="ID do convite">
          <input className={inputClass} value={invitationId} readOnly required />
        </Field>
        {mode === "signup" ? (
          <Field label="Nome">
            <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
        ) : null}
        <Field label="E-mail">
          <input className={inputClass} value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
        </Field>
        <Field label="Senha">
          <input
            className={inputClass}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            required
          />
        </Field>
        <PrimaryButton type="submit" disabled={busy || !invitationId}>
          <span className="inline-flex items-center gap-2">
            {accepted ? <Check size={16} /> : busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            {accepted ? "Convite aceito" : actionLabel}
          </span>
        </PrimaryButton>
      </form>
    </AuthSurface>
  );
}

function AuthSurface({
  eyebrow,
  title,
  subtitle,
  error,
  children
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  error: string | null;
  children: React.ReactNode;
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-[#eef3f7] px-4 py-8">
      <motion.section
        initial={{ opacity: 0, y: 12, scale: 0.99 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        className="w-full max-w-md rounded-lg border border-slateLine bg-white p-5 shadow-panel"
      >
        <div className="mb-5 flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-ink text-white">
            <School size={20} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-normal text-lake">{eyebrow}</p>
            <h1 className="mt-1 text-xl font-semibold">{title}</h1>
            <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
          </div>
        </div>
        <AnimatePresence>
          {error ? (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mb-4 rounded-md border border-rose/30 bg-rose/10 px-3 py-2 text-sm text-rose"
            >
              {error}
            </motion.div>
          ) : null}
        </AnimatePresence>
        {children}
      </motion.section>
    </main>
  );
}

async function authFetch(path: string, body: Record<string, unknown>) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(body)
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(data?.message ?? data?.detail ?? text ?? `HTTP ${response.status}`);
  }
  return data;
}
