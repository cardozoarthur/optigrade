import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PlanningDashboard from "@/components/planning/planning-dashboard";

vi.stubGlobal(
  "fetch",
  vi.fn((url: string) => {
    const body = url.includes("/optimization/runs")
      ? []
      : url.includes("/courses")
        ? []
        : url.includes("/professors")
          ? []
          : url.includes("/rooms")
            ? []
            : [];
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
  })
);

describe("Home", () => {
  it("renders dashboard shell", () => {
    render(<PlanningDashboard />);
    expect(screen.getByText("OptiGrade")).toBeTruthy();
    expect(screen.getByText("Gerador")).toBeTruthy();
  });
});
