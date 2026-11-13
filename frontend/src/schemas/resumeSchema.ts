import { z } from "zod";

export const personalInfoSchema = z.object({
  full_name: z.string().trim().min(2, "Informe o nome completo."),
  email: z
    .string()
    .trim()
    .refine((v) => v === "" || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), "E-mail inválido."),
  phone: z.string().trim(),
  linkedin: z.string().trim(),
  location: z.string().trim(),
  evidence_quote: z.string(),
});

export const experienceItemSchema = z.object({
  role: z.string().trim().min(2, "Informe o cargo."),
  company: z.string().trim(),
  period: z.string().trim(),
  location: z.string().trim(),
  responsibilities: z.array(z.string()),
  achievements: z.array(z.string()),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const educationItemSchema = z.object({
  degree: z.string().trim().min(2, "Informe o curso ou formação."),
  institution: z.string().trim(),
  period: z.string().trim(),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const certificationItemSchema = z.object({
  name: z.string().trim().min(2, "Informe o nome da certificação."),
  issuer: z.string().trim(),
  year: z.string().trim(),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const skillItemSchema = z.object({
  name: z.string().trim().min(1, "Informe a competência."),
  category: z.string().trim(),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const languageItemSchema = z.object({
  language: z.string().trim().min(2, "Informe o idioma."),
  proficiency: z.string().trim(),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const projectItemSchema = z.object({
  name: z.string().trim().min(2, "Informe o nome do projeto."),
  description: z.string().trim(),
  technologies: z.array(z.string()),
  url: z.string().trim(),
  evidence_quote: z.string(),
  evidence_verified: z.boolean(),
});

export const parsedResumeSchema = z.object({
  personal_info: personalInfoSchema,
  professional_summary: z.string(),
  summary_evidence_quote: z.string(),
  experiences: z.array(experienceItemSchema),
  education: z.array(educationItemSchema),
  certifications: z.array(certificationItemSchema),
  technical_skills: z.array(skillItemSchema),
  languages: z.array(languageItemSchema),
  projects: z.array(projectItemSchema),
});

export type ParsedResumeFormValues = z.infer<typeof parsedResumeSchema>;
