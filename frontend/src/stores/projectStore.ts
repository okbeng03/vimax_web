import { create } from "zustand";
import type { ProjectListItem, ProjectDetail } from "../types/project";
import type { Template } from "../api/templates";
import * as projectsApi from "../api/projects";
import * as templatesApi from "../api/templates";

interface ProjectState {
  projects: ProjectListItem[];
  total: number;
  currentProject: ProjectDetail | null;
  templates: Template[];
  loading: boolean;
  error: string | null;

  fetchProjects: (params?: { status?: string; search?: string; page?: number }) => Promise<void>;
  fetchProject: (id: number, opts?: { silent?: boolean }) => Promise<void>;
  updateProjectStatus: (status: string, extra?: Partial<ProjectDetail>) => void;
  createProject: (body: Parameters<typeof projectsApi.createProject>[0]) => Promise<number>;
  updateConfig: (id: number, body: { yaml_content: string; config_py_content: string }) => Promise<void>;
  deleteProject: (id: number) => Promise<void>;
  fetchTemplates: () => Promise<void>;
  clearError: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  total: 0,
  currentProject: null,
  templates: [],
  loading: false,
  error: null,

  fetchProjects: async (params) => {
    set({ loading: true, error: null });
    try {
      const data = await projectsApi.fetchProjects(params);
      set({ projects: data.projects, total: data.total, loading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  fetchProject: async (id, opts) => {
    if (!opts?.silent) set({ loading: true, error: null });
    try {
      const project = await projectsApi.fetchProject(id);
      set({ currentProject: project, loading: false });
    } catch (err: unknown) {
      set({ error: (err as Error).message, loading: opts?.silent ? undefined : false });
    }
  },

  updateProjectStatus: (status, extra) => {
    set((state) => ({
      currentProject: state.currentProject
        ? { ...state.currentProject, status, ...extra } as ProjectDetail
        : null,
    }));
  },

  createProject: async (body) => {
    set({ loading: true, error: null });
    try {
      const result = await projectsApi.createProject(body);
      set({ loading: false });
      return result.id;
    } catch (err: unknown) {
      set({ error: (err as Error).message, loading: false });
      throw err;
    }
  },

  updateConfig: async (id, body) => {
    set({ error: null });
    try {
      await projectsApi.updateProjectConfig(id, body);
    } catch (err: unknown) {
      set({ error: (err as Error).message });
      throw err;
    }
  },

  deleteProject: async (id) => {
    set({ error: null });
    try {
      await projectsApi.deleteProject(id);
      set((state) => ({
        projects: state.projects.filter((p) => p.id !== id),
        currentProject: state.currentProject?.id === id ? null : state.currentProject,
      }));
    } catch (err: unknown) {
      set({ error: (err as Error).message });
    }
  },

  fetchTemplates: async () => {
    try {
      const data = await templatesApi.fetchTemplates();
      set({ templates: data.templates });
    } catch (err: unknown) {
      set({ error: (err as Error).message });
    }
  },

  clearError: () => set({ error: null }),
}));
