import { describe, expect, it } from "vitest";
import { roleCan } from "@/lib/auth/permissions";
import { resolveBffPermission } from "@/lib/bff-permissions";

describe("resolveBffPermission", () => {
  it("keeps student self endpoints scoped to the authenticated student", () => {
    const ownPermission = resolveBffPermission(
      ["students", "student-a", "course-requests"],
      "POST",
      { professorId: null, studentId: "student-a" }
    );
    const otherPermission = resolveBffPermission(
      ["students", "student-b", "course-requests"],
      "POST",
      { professorId: null, studentId: "student-a" }
    );

    expect(ownPermission).toBe("students:self");
    expect(otherPermission).toBe("students:write");
    expect(roleCan("student", ownPermission)).toBe(true);
    expect(roleCan("student", otherPermission)).toBe(false);
  });

  it("keeps professor self endpoints scoped to the authenticated professor", () => {
    const ownPermission = resolveBffPermission(
      ["professors", "prof-a", "constraints"],
      "POST",
      { professorId: "prof-a", studentId: null }
    );
    const otherPermission = resolveBffPermission(
      ["professors", "prof-b", "constraints"],
      "POST",
      { professorId: "prof-a", studentId: null }
    );

    expect(ownPermission).toBe("faculty:self");
    expect(otherPermission).toBe("faculty:write");
    expect(roleCan("professor", ownPermission)).toBe(true);
    expect(roleCan("professor", otherPermission)).toBe(false);
  });
});
