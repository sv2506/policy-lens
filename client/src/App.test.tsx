import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

describe("PolicyLens", () => {
  it("renders the grounded assistant shell", () => {
    render(<App />);
    expect(screen.getByText("PolicyLens")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /ask a policy question/i })).toBeInTheDocument();
  });
});
