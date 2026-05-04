import { NextRequest, NextResponse } from "next/server";
import { revalidateTag } from "next/cache";
import { getAcademicSession } from "@/lib/auth/session";
import { roleCan, type PermissionKey } from "@/lib/auth/permissions";
import { getBffMutationTags, getBffReadCachePolicy } from "@/lib/cache-tags";

export const runtime = "nodejs";

const backendUrl =
  process.env.FASTAPI_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8002";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

async function proxy(request: NextRequest, context: RouteContext) {
  const session = await getAcademicSession();
  if (!session) {
    return NextResponse.json({ detail: "Sessao obrigatoria" }, { status: 401 });
  }

  const { path } = await context.params;
  const permission = resolvePermission(path, request.method, {
    studentId: session.user.studentId ?? null
  });

  if (!roleCan(session.role, permission)) {
    return NextResponse.json(
      {
        detail: "Usuario sem permissao para esta operacao",
        permission,
        role: session.role
      },
      { status: 403 }
    );
  }

  const target = new URL(path.join("/"), ensureSlash(backendUrl));
  target.search = request.nextUrl.search;

  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();
  const cachePolicy = ["GET", "HEAD"].includes(request.method)
    ? getBffReadCachePolicy(path, session.organization?.id)
    : null;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", request.headers.get("accept") ?? "application/json");
  if (!cachePolicy) {
    headers.set("x-optigrade-user-id", session.user.id);
    headers.set("x-optigrade-user-email", session.user.email);
  }
  headers.set("x-optigrade-role", session.role);
  if (session.organization?.id) headers.set("x-optigrade-organization-id", session.organization.id);
  if (process.env.OPTIGRADE_INTERNAL_API_SECRET) {
    headers.set("x-optigrade-internal-secret", process.env.OPTIGRADE_INTERNAL_API_SECRET);
  }

  const fetchInit: RequestInit & { next?: { revalidate?: number; tags?: string[] } } = {
    method: request.method,
    body: body || undefined,
    headers,
    ...(cachePolicy
      ? {
          cache: "force-cache" as RequestCache,
          next: {
            revalidate: cachePolicy.revalidate,
            tags: cachePolicy.tags
          }
        }
      : {
          cache: "no-store" as RequestCache
        })
  };

  const response = await fetch(target, fetchInit);

  if (response.ok && !["GET", "HEAD"].includes(request.method)) {
    for (const tag of getBffMutationTags(path, session.organization?.id)) {
      revalidateTag(tag);
    }
  }

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.set("cache-control", "private, no-store");
  responseHeaders.append("vary", "Cookie");

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders
  });
}

function ensureSlash(value: string) {
  return value.endsWith("/") ? value : `${value}/`;
}

function resolvePermission(
  path: string[],
  method: string,
  self: { studentId: string | null }
): PermissionKey {
  const [resource, id, child] = path;
  const write = !["GET", "HEAD"].includes(method);

  if (resource === "health" || resource === "readiness") return "readiness:read";
  if (resource === "optimization") {
    if (!write) return "optimization:read";
    return child === "manual-adjustments" || path.includes("manual-adjustments")
      ? "optimization:adjust"
      : "optimization:run";
  }
  if (resource === "professors") {
    if (id && ["availability", "course-preferences", "constraints", "preference-batch"].includes(child ?? "")) {
      return "faculty:self";
    }
    return write ? "faculty:write" : "faculty:read";
  }
  if (resource === "students") {
    if (!id && !write) return "students:self";
    if (id && ["suggestions", "course-requests", "history"].includes(child ?? "")) return "students:self";
    if (id && self.studentId === id) return write ? "students:self" : "students:self";
    return write ? "students:write" : "students:read";
  }
  if (resource === "imports") return "catalog:write";
  if (["courses", "campuses", "degree-programs", "course-restrictions", "rooms", "timeslots"].includes(resource)) {
    return write ? "catalog:write" : "catalog:read";
  }

  return write ? "catalog:write" : "catalog:read";
}
