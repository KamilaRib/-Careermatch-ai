import { api } from "@/lib/api";
import type {
  ParsedResumeData,
  ResumeSessionState,
  ResumeUploadResponse,
} from "@/types/resume";

export const resumeService = {
  getCurrent: () => api<ResumeSessionState>("/resumes/current"),

  uploadFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<ResumeUploadResponse>("/resumes/upload", {
      method: "POST",
      body: form,
    });
  },

  parse: (params?: { text?: string; use_deterministic_only?: boolean }) =>
    api<ResumeSessionState>("/resumes/parse", {
      method: "POST",
      json: params ?? {},
    }),

  confirm: (data: ParsedResumeData, confirmed = true) =>
    api<ResumeSessionState>("/resumes/current", {
      method: "PUT",
      json: { data, confirmed },
    }),
};
