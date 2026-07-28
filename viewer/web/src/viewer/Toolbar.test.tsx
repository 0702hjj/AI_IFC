import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Toolbar } from "./Toolbar";
import { SectionControl } from "./SectionControl";

describe("Toolbar", () => {
  it("renders nothing without a viewer context", () => {
    const { container } = render(<Toolbar id="m_1" />);
    expect(container.firstChild).toBeNull();
  });
});

describe("SectionControl", () => {
  it("renders nothing without a viewer context", () => {
    const { container } = render(<SectionControl enabled />);
    expect(container.firstChild).toBeNull();
  });
});
