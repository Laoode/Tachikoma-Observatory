"use client";

import { create } from "zustand";
import type { BenchmarkRun } from "@/lib/benchmark/types";

interface BenchmarkStore {
  currentModelId: string;

  selectedScenarioId: string | null;

  currentRun: BenchmarkRun | null;

  setCurrentModel: (modelId: string) => void;

  setSelectedScenario: (
    scenarioId: string
  ) => void;

  setCurrentRun: (
    run: BenchmarkRun | null
  ) => void;
}

export const useBenchmarkStore =
  create<BenchmarkStore>((set) => ({
    currentModelId: "qwen3.5-4b",

    selectedScenarioId: null,

    currentRun: null,

    setCurrentModel: (modelId) =>
      set({
        currentModelId: modelId,
      }),

    setSelectedScenario: (
      scenarioId
    ) =>
      set({
        selectedScenarioId: scenarioId,
      }),

    setCurrentRun: (run) =>
      set({
        currentRun: run,
      }),
  }));