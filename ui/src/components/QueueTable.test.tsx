import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { QueueTable } from "./QueueTable";
import { queueRows } from "../test/fixtures";

function renderTable() {
  return render(
    <MemoryRouter>
      <QueueTable cases={queueRows} />
    </MemoryRouter>,
  );
}

describe("QueueTable", () => {
  it("lists every open case with its merchant", () => {
    renderTable();
    expect(screen.getByText("merch_standard_branch")).toBeInTheDocument();
    expect(screen.getByText("merch_demo_electronics_risky")).toBeInTheDocument();
    expect(screen.getByText("merch_standard_partial")).toBeInTheDocument();
  });

  it("filters by risk band", async () => {
    const user = userEvent.setup();
    renderTable();
    await user.selectOptions(screen.getByLabelText("Risk"), "HIGH");

    expect(screen.getByText("merch_demo_electronics_risky")).toBeInTheDocument();
    expect(screen.queryByText("merch_standard_branch")).not.toBeInTheDocument();
  });

  it("filters by robustness", async () => {
    const user = userEvent.setup();
    renderTable();
    await user.selectOptions(screen.getByLabelText("Robustness"), "ROBUST");

    expect(screen.getByText("merch_standard_partial")).toBeInTheDocument();
    expect(screen.queryByText("merch_standard_branch")).not.toBeInTheDocument();
  });

  it("sorts HIGH risk before MEDIUM", () => {
    renderTable();
    const rows = screen.getAllByRole("row").slice(1); // skip header
    expect(rows[0]).toHaveTextContent("merch_demo_electronics_risky"); // HIGH
  });
});
