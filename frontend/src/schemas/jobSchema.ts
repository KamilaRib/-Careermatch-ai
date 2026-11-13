import { z } from "zod";

export const jobRequirementItemSchema = z.object({
  name: z.string().trim().min(2, "Informe o requisito."),
  category: z.enum([
    "competencias_tecnicas",
    "experiencia_profissional",
    "formacao_certificacoes",
    "competencias_comportamentais",
    "idiomas",
    "outros",
  ]),
  importance: z.enum(["obrigatorio", "desejavel", "contextual", "nao_especificado"]),
  is_eliminatory: z.boolean(),
  min_years: z.number().int().min(0).max(40).nullable().optional(),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const parsedJobSchema = z.object({
  title: z.string().trim().min(2, "Informe o cargo da vaga."),
  company: z.string().trim(),
  location: z.string().trim(),
  work_model: z.string().trim(),
  seniority: z.string().trim(),
  experience_years_required: z.string().trim(),
  education_required: z.string().trim(),
  responsibilities: z.array(z.string()),
  requirements: z.array(jobRequirementItemSchema),
  technologies: z.array(z.string()),
  languages: z.array(z.string()),
  keywords: z.array(z.string()),
});

export type ParsedJobFormValues = z.infer<typeof parsedJobSchema>;
