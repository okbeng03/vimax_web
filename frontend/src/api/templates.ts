import client from "./client";

export interface Template {
  id: number;
  name: string;
  display_name: string;
  description: string;
  directory_name: string;
  is_builtin: boolean;
  created_at: string;
}

export interface TemplateCreate {
  name: string;
  display_name: string;
  description: string;
  directory_name: string;
}

export interface TemplateUpdate {
  display_name?: string;
  description?: string;
  directory_name?: string;
}

export async function fetchTemplates(): Promise<{ templates: Template[] }> {
  const { data } = await client.get("/templates");
  return data;
}

export async function createTemplate(body: TemplateCreate): Promise<Template> {
  const { data } = await client.post("/templates", body);
  return data;
}

export async function updateTemplate(id: number, body: TemplateUpdate): Promise<Template> {
  const { data } = await client.patch(`/templates/${id}`, body);
  return data;
}

export async function deleteTemplate(id: number): Promise<void> {
  await client.delete(`/templates/${id}`);
}
