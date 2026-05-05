import { NextRequest, NextResponse } from "next/server";
import {
  isAllowedPublicPresentationPath,
  publicRequestBody
} from "@/lib/public-presentation-bff";

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

function ensureSlash(value: string) {
  return value.endsWith("/") ? value : `${value}/`;
}
