import { NextRequest, NextResponse } from "next/server";
import { bootstrapAdminExists } from "@/lib/auth/bootstrap";
import { authDb } from "@/lib/auth/db";
import { auth } from "@/lib/auth/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type BootstrapBody = {
  name?: string;
  email?: string;
  password?: string;
  organizationName?: string;
  slug?: string;
};

export async function GET() {
  return NextResponse.json({ available: !(await bootstrapAdminExists()) });
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as BootstrapBody;
  const name = clean(body.name);
  const email = clean(body.email).toLowerCase();
  const password = body.password ?? "";
  const organizationName = clean(body.organizationName);
  const slug = clean(body.slug);

  if (!name || !email || !organizationName || !slug || password.length < 8) {
    return NextResponse.json(
      { detail: "Nome, e-mail, senha com 8+ caracteres, organizacao e slug sao obrigatorios." },
      { status: 400 }
    );
  }

  const lock = await authDb.connect();
  try {
    await lock.query("begin");
    await lock.query("select pg_advisory_xact_lock(hashtext('optigrade-bootstrap-admin'))");
    if (await bootstrapAdminExists()) {
      await lock.query("rollback");
      return NextResponse.json({ detail: "O primeiro administrador ja foi configurado." }, { status: 409 });
    }

    const signedUp = await auth.api.signUpEmail({
      body: {
        name,
        email,
        password,
        profileType: "admin"
      }
    });

    await auth.api.createOrganization({
      body: {
        name: organizationName,
        slug,
        userId: signedUp.user.id,
        kind: "academic-unit",
        metadata: {
          product: "OptiGrade",
          pilot: true,
          bootstrap: true
        }
      }
    });

    await lock.query("commit");
    return NextResponse.json({ ok: true, email });
  } catch (error) {
    await lock.query("rollback").catch(() => undefined);
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ detail: message }, { status: 400 });
  } finally {
    lock.release();
  }
}

function clean(value: string | undefined) {
  return value?.trim() ?? "";
}
