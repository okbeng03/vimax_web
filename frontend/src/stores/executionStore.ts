import { create } from "zustand";
import type { Step } from "../types/step";
import * as stepsApi from "../api/steps";

interface ExecutionState {
  steps: Step[];
  isRunning: boolean;
  currentStepName: string | null;
  loading: boolean;
  error: string | null;

  fetchSteps: (projectId: number) => Promise<void>;
  execute: (projectId: number, action: string, stepName?: string) => Promise<void>;
  kill: (projectId: number) => Promise<void>;
  clearError: () => void;
}

export const useExecutionStore = create<ExecutionState>((set) => ({
  steps: [],
  isRunning: false,
  currentStepName: null,
  loading: false,
  error: null,

  fetchSteps: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const data = await stepsApi.fetchSteps(projectId);
      set({ steps: data.steps, loading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  execute: async (projectId, action, stepName) => {
    set({ error: null });
    try {
      const result = await stepsApi.executeSteps(projectId, action, stepName);
      set({ isRunning: true, currentStepName: result.current_step_name });
    } catch (err: unknown) {
      set({ error: (err as Error).message });
      throw err;
    }
  },

  kill: async (projectId) => {
    set({ error: null });
    try {
      await stepsApi.killSteps(projectId);
      set({ isRunning: false, currentStepName: null });
    } catch (err: unknown) {
      set({ error: (err as Error).message });
    }
  },

  clearError: () => set({ error: null }),
}));
