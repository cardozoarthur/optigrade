import { describe, expect, it } from "vitest";
import { nextSlide, previousSlide, resolveSlide } from "@/components/trabalho/presentation-data";

describe("trabalho slide routing", () => {
  it("resolves numeric aliases to canonical slugs", () => {
    expect(resolveSlide("slide1")).toBe("apresentacao");
    expect(resolveSlide("slide13")).toBe("conclusao");
  });

  it("keeps keyboard navigation inside the routed slide sequence", () => {
    expect(nextSlide("apresentacao")).toBe("contexto-historico");
    expect(previousSlide("contexto-historico")).toBe("apresentacao");
    expect(nextSlide("conclusao")).toBe("conclusao");
  });
});
