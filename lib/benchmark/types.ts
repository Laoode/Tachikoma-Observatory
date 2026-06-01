export type RunStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed";

export type ScenarioStatus =
  | "pending"
  | "running"
  | "pass"
  | "partial"
  | "fail";

export interface ToolCall {
  toolName: string;
  arguments: Record<string, unknown>;
}

export interface ScenarioResult {
  scenarioId: string;

  status: ScenarioStatus;

  score: number;

  latencyMs: number;

  promptTokens: number;

  completionTokens: number;

  toolCalls: ToolCall[];

  finalResponse: string;
}

export interface BenchmarkRun {
  id: string;

  modelId: string;

  status: RunStatus;

  currentScenario: number;

  totalScenarios: number;

  promptTokens: number;

  completionTokens: number;

  toolCalls: number;

  hallucinatedCalls: number;

  startedAt?: string;

  completedAt?: string;

  results: ScenarioResult[];
}