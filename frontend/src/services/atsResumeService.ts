import { API_BASE, api } from "@/lib/api";
import type {
  ATSResumeResult,
  CurrentATSResumeResponse,
  ExportFormat,
} from "@/types/atsResume";
import type { ParsedResumeData } from "@/types/resume";

export async function generateATSResume(
  useDeterministicOnly = false,
): Promise<ATSResumeResult> {
  return api<ATSResumeResult>("/ats-resume/generate", {
    method: "POST",
    json: { use_deterministic_only: useDeterministicOnly },
  });
}

export async function getCurrentATSResume(): Promise<CurrentATSResumeResponse> {
  return api<CurrentATSResumeResponse>("/ats-resume/current", {
    method: "GET",
  });
}

export async function updateAndApproveATSResume(
  optimizedData: ParsedResumeData,
  approved = true,
): Promise<ATSResumeResult> {
  return api<ATSResumeResult>("/ats-resume/current", {
    method: "PUT",
    json: {
      optimized_data: optimizedData,
      approved,
    },
  });
}

export function getATSExportUrl(format: ExportFormat): string {
  const base = API_BASE.replace(/\/$/, "");
  return `${base}/ats-resume/export/${format}`;
}
