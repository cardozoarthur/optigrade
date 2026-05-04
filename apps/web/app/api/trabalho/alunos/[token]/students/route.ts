import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const backendUrl =
  process.env.FASTAPI_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8002";

type RouteContext = {
  params: Promise<{ token: string }>;
};

export async function POST(request: NextRequest, context: RouteContext) {
  const { token } = await context.params;
  return proxy(request, `presentation/student-tokens/${token}/students`);
}

async function proxy(request: NextRequest, path: string) {
  const target = new URL(path, ensureSlash(backendUrl));
  const headers = new Headers({
    accept: "application/json",
    "content-type": request.headers.get("content-type") ?? "application/json"
  });
  if (process.env.OPTIGRADE_INTERNAL_API_SECRET) {
    headers.set("x-optigrade-internal-secret", process.env.OPTIGRADE_INTERNAL_API_SECRET);
  }
  const response = await fetch(target, {
    method: "POST",
    body: await request.text(),
    headers,
    cache: "no-store"
  });
  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders(response)
  });
}

function responseHeaders(response: Response) {
  const headers = new Headers(response.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");
  headers.set("cache-control", "private, no-store");
  return headers;
}

function ensureSlash(value: string) {
  return value.endsWith("/") ? value : `${value}/`;
}
