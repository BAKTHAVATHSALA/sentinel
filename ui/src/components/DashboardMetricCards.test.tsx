import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DashboardMetricCards } from "./DashboardMetricCards";
import type { CaseDashboardMetrics } from "../lib/dashboardMetrics";

const METRICS: CaseDashboardMetrics = {
  totalCases: 12,
  openCases: 5,
  closedCases: 7,
  blockHoldCases: 2,
  escalatedToSenior: 3,
};

const ZERO_METRICS: CaseDashboardMetrics = {
  totalCases: 0,
  openCases: 0,
  closedCases: 0,
  blockHoldCases: 0,
  escalatedToSenior: 0,
};

describe("DashboardMetricCards", () => {
  it("shows the four analyst core metrics with their actual counts", () => {
    render(<DashboardMetricCards metrics={METRICS} showEscalatedToSenior={true} />);
    expect(screen.getByTestId("dashboard-metric-Total Cases")).toHaveTextContent("12");
    expect(screen.getByTestId("dashboard-metric-Open Cases")).toHaveTextContent("5");
    expect(screen.getByTestId("dashboard-metric-Closed Cases")).toHaveTextContent("7");
    expect(screen.getByTestId("dashboard-metric-Block & Hold")).toHaveTextContent("2");
  });

  it("shows Escalated to Senior only when showEscalatedToSenior is true (Analyst dashboard)", () => {
    render(<DashboardMetricCards metrics={METRICS} showEscalatedToSenior={true} />);
    expect(screen.getByTestId("dashboard-metric-Escalated to Senior")).toHaveTextContent("3");
  });

  it("never renders Escalated to Senior when showEscalatedToSenior is false (Senior dashboard)", () => {
    render(<DashboardMetricCards metrics={METRICS} showEscalatedToSenior={false} />);
    expect(screen.queryByTestId("dashboard-metric-Escalated to Senior")).not.toBeInTheDocument();
    expect(screen.queryByText("Escalated to Senior")).not.toBeInTheDocument();
  });

  it("renders zero as the literal digit 0, never a placeholder like '--'", () => {
    render(<DashboardMetricCards metrics={ZERO_METRICS} showEscalatedToSenior={true} />);
    expect(screen.getByTestId("dashboard-metric-Total Cases")).toHaveTextContent("0");
    expect(screen.queryByText("--")).not.toBeInTheDocument();
    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
  });

  it("does not render any chart, percentage, or trend indicator", () => {
    render(<DashboardMetricCards metrics={METRICS} showEscalatedToSenior={true} />);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/vs last week/i)).not.toBeInTheDocument();
    expect(document.querySelector("svg")).not.toBeInTheDocument();
    expect(document.querySelector("canvas")).not.toBeInTheDocument();
  });
});
