import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
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

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (!isAllowedPublicPresentationPath(path, request.method)) {
    return NextResponse.json({ detail: "Endpoint publico nao permitido" }, { status: 403 });
  }

  const target = new URL(path.join("/"), ensureSlash(backendUrl));
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", request.headers.get("accept") ?? "application/json");
  headers.set("x-optigrade-role", "presentation");
  if (process.env.OPTIGRADE_INTERNAL_API_SECRET) {
    headers.set("x-optigrade-internal-secret", process.env.OPTIGRADE_INTERNAL_API_SECRET);
  }

  const response = await fetch(target, {
    method: request.method,
    body: request.method === "GET" ? undefined : await publicRequestBody(request, path),
    headers,
    cache: "no-store"
  });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.set("cache-control", "private, no-store");

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders
  });
}

async function publicRequestBody(request: NextRequest, path: string[]) {
  if (path[0] !== "optimization" || path[1] !== "runs" || request.method !== "POST") {
    return request.text();
  }
  const rawBody = await request.text();
  let data: Record<string, unknown> = {};
  try {
    data = rawBody ? JSON.parse(rawBody) : {};
  } catch {
    data = {};
  }
  const parameters =
    typeof data.parameters === "object" && data.parameters
      ? (data.parameters as Record<string, unknown>)
      : {};
  return JSON.stringify({
    semester: "2026/2",
    profile: "balanced",
    parameters: {
      student_demand_only: true,
      auto_enrollment: true,
      enrollment_stage: "pre_enrollment",
      source: "trabalho",
      presentation_run_id: typeof parameters.presentation_run_id === "string" ? parameters.presentation_run_id : undefined,
      requested_at: typeof parameters.requested_at === "string" ? parameters.requested_at : undefined
    }
  });
}

function isAllowedPublicPresentationPath(path: string[], method: string) {
  const [resource, id, child] = path;
  if (resource === "presentation") {
    if (method === "GET" && id === "stats") return true;
    if (method === "POST" && ["teacher-link", "student-link"].includes(id ?? "") && path.length === 2) {
      return true;
    }
    if (method === "POST" && ["teacher-link", "student-link"].includes(id ?? "") && child && path[3] === "revoke") {
      return true;
    }
  }
  if (method === "GET" && ["courses", "professors", "rooms", "timeslots", "campuses"].includes(resource ?? "")) {
    return path.length === 1;
  }
  if (resource === "optimization" && id === "runs") {
    if (method === "POST" && path.length === 2) return true;
    if (method === "GET" && path.length === 3) return true;
    if (method === "GET" && path.length === 4 && path[3] === "assignments") return true;
  }
  return false;
}

function ensureSlash(value: string) {
  return value.endsWith("/") ? value : `${value}/`;
}
