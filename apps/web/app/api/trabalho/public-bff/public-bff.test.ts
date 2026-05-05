import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import {
  isAllowedPublicPresentationPath,
  publicRequestBody
} from "@/lib/public-presentation-bff";

describe("public presentation BFF", () => {
  it("sanitizes optimization runs to the balanced asynchronous pilot profile", async () => {
    const request = new NextRequest("https://optigrade.test/api/trabalho/public-bff/optimization/runs", {
      method: "POST",
      body: JSON.stringify({
        semester: "2030/1",
        profile: "deep",
        parameters: {
          student_demand_only: false,
          auto_enrollment: false,
          enrollment_stage: "correction",
          source: "external",
          presentation_run_id: "client-run",
          requested_at: "2026-05-05T00:00:00.000Z"
        }
      })
    });

    const body = JSON.parse(await publicRequestBody(request, ["optimization", "runs"]));

    expect(body).toEqual({
      semester: "2026/2",
      profile: "balanced",
      parameters: {
        student_demand_only: true,
        auto_enrollment: true,
        enrollment_stage: "pre_enrollment",
        source: "trabalho",
        presentation_run_id: "client-run",
        requested_at: "2026-05-05T00:00:00.000Z"
      }
    });
  });

  it("only exposes public presentation read and action endpoints", () => {
    expect(isAllowedPublicPresentationPath(["optimization", "runs"], "POST")).toBe(true);
    expect(isAllowedPublicPresentationPath(["optimization", "runs", "run-id"], "GET")).toBe(true);
    expect(isAllowedPublicPresentationPath(["optimization", "runs", "run-id", "assignments"], "GET")).toBe(true);
    expect(isAllowedPublicPresentationPath(["courses"], "GET")).toBe(true);
    expect(isAllowedPublicPresentationPath(["courses"], "POST")).toBe(false);
    expect(isAllowedPublicPresentationPath(["optimization", "runs", "run-id"], "DELETE")).toBe(false);
  });
});
