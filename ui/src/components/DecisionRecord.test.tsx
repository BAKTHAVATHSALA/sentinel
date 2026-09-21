import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DecisionRecord } from "./DecisionRecord";
import { finalizedCase } from "../test/fixtures";
import { clearAnalystIdentity, setAnalystIdentity } from "../lib/analystIdentity";

describe("DecisionRecord", () => {
  afterEach(() => {
    clearAnalystIdentity();
  });

  it("never renders the raw Firebase UID -- uses the server-resolved caller display name instead", () => {
    setAnalystIdentity({ displayName: "Priya Nair", role: "ANALYST" });
    render(<DecisionRecord caseDoc={finalizedCase} />);

    expect(screen.getByText(/Priya Nair recorded:/)).toBeInTheDocument();
    expect(screen.queryByText(finalizedCase.assigned_analyst_id ?? "__none__")).not.toBeInTheDocument();
  });

  it("falls back to generic wording if identity hasn't loaded yet, still never showing a raw UID", () => {
    render(<DecisionRecord caseDoc={finalizedCase} />);
    expect(screen.getByText(/This analyst recorded:/)).toBeInTheDocument();
  });

  it("shows CLEAR in teal/stable", () => {
    render(<DecisionRecord caseDoc={{ ...finalizedCase, final_disposition: "CLEAR" }} />);
    const value = screen.getByText("CLEAR");
    expect(value).toHaveStyle({ color: "var(--color-stable)" });
  });

  it("shows BLOCK_HOLD in red/critical, consistent everywhere else BLOCK_HOLD is shown", () => {
    render(<DecisionRecord caseDoc={{ ...finalizedCase, final_disposition: "BLOCK_HOLD" }} />);
    const value = screen.getByText("BLOCK_HOLD");
    expect(value).toHaveStyle({ color: "var(--color-critical)" });
  });
});
