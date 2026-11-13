import { useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Plus,
  Quote,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { parsedResumeSchema, type ParsedResumeFormValues } from "@/schemas/resumeSchema";
import type { EvidenceValidationReport, ExtractionMethod, ParsedResumeData } from "@/types/resume";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";

interface ResumeReviewFormProps {
  data: ParsedResumeData;
  extractionMethod: ExtractionMethod | null;
  providerUsed: string | null;
  fallbackReason: string | null;
  evidenceReport: EvidenceValidationReport;
  confirmed: boolean;
  isSaving: boolean;
  onConfirm: (values: ParsedResumeData) => void;
}

function EvidenceCaption({ quote, verified }: { quote: string; verified?: boolean }) {
  if (!quote && verified !== false) return null;
  return (
    <div className="bg-muted/60 mt-2 flex items-start gap-2 rounded-md border px-3 py-2 text-xs">
      <Quote className="text-muted-foreground mt-0.5 size-3.5 shrink-0" aria-hidden />
      <div className="flex-1">
        <span className="font-medium">Evidência no documento original: </span>
        <span className="text-muted-foreground italic">{quote || "Nenhuma citação literal associada."}</span>
      </div>
      {verified === false ? (
        <Badge variant="accent" title="Não localizado literalmente no texto original">
          <AlertTriangle /> Revisar
        </Badge>
      ) : (
        <Badge variant="success">
          <CheckCircle2 /> Verificado
        </Badge>
      )}
    </div>
  );
}

export function ResumeReviewForm({
  data,
  extractionMethod,
  providerUsed,
  fallbackReason,
  evidenceReport,
  confirmed,
  isSaving,
  onConfirm,
}: ResumeReviewFormProps) {
  const form = useForm<ParsedResumeFormValues>({
    resolver: zodResolver(parsedResumeSchema),
    defaultValues: data,
  });

  useEffect(() => {
    form.reset(data);
  }, [data, form]);

  const experiences = useFieldArray({ control: form.control, name: "experiences" });
  const education = useFieldArray({ control: form.control, name: "education" });
  const skills = useFieldArray({ control: form.control, name: "technical_skills" });
  const certifications = useFieldArray({ control: form.control, name: "certifications" });
  const languages = useFieldArray({ control: form.control, name: "languages" });
  const projects = useFieldArray({ control: form.control, name: "projects" });

  const errors = form.formState.errors;

  return (
    <form
      onSubmit={form.handleSubmit((values) => onConfirm(values))}
      className="flex flex-col gap-6"
      noValidate
    >
      {/* Transparency Banner: LLM vs Deterministic Fallback */}
      <Card className="bg-secondary/40">
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {extractionMethod === "llm" ? (
                <Badge variant="default">
                  <Sparkles /> Extraído por IA ({providerUsed})
                </Badge>
              ) : (
                <Badge variant="accent">
                  <Cpu /> Extração determinística local (modo sem IA)
                </Badge>
              )}
              <Badge variant="outline">
                Evidências verificadas: {evidenceReport.verified_items}/{evidenceReport.total_items_checked}
              </Badge>
              {confirmed && (
                <Badge variant="success">
                  <ShieldCheck /> Dados confirmados pelo usuário
                </Badge>
              )}
            </div>
          </div>

          {extractionMethod === "deterministic_fallback" && (
            <p className="text-muted-foreground text-xs">
              Os dados abaixo foram organizados por regras determinísticas (sem modelo de linguagem).
              {fallbackReason ? ` Motivo: ${fallbackReason}` : ""} Revise os campos antes de confirmar.
            </p>
          )}

          {evidenceReport.unverified_warnings.length > 0 && (
            <div
              role="alert"
              className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950"
            >
              <p className="font-semibold">Atenção — itens sem comprovação textual literal:</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {evidenceReport.unverified_warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dados Pessoais */}
      <Card>
        <CardHeader>
          <CardTitle>Dados pessoais e contato</CardTitle>
          <CardDescription>Revise seus dados básicos de identificação.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="pi-full-name">Nome completo *</Label>
            <Input id="pi-full-name" {...form.register("personal_info.full_name")} />
            {errors.personal_info?.full_name && (
              <p className="text-destructive text-xs">{errors.personal_info.full_name.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pi-email">E-mail</Label>
            <Input id="pi-email" type="email" {...form.register("personal_info.email")} />
            {errors.personal_info?.email && (
              <p className="text-destructive text-xs">{errors.personal_info.email.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pi-phone">Telefone</Label>
            <Input id="pi-phone" {...form.register("personal_info.phone")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pi-linkedin">LinkedIn</Label>
            <Input id="pi-linkedin" {...form.register("personal_info.linkedin")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pi-location">Localização</Label>
            <Input id="pi-location" {...form.register("personal_info.location")} />
          </div>
          <div className="sm:col-span-2">
            <EvidenceCaption quote={form.watch("personal_info.evidence_quote")} verified />
          </div>
        </CardContent>
      </Card>

      {/* Resumo Profissional */}
      <Card>
        <CardHeader>
          <CardTitle>Resumo profissional</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <Label htmlFor="prof-summary" className="sr-only">
            Resumo profissional
          </Label>
          <Textarea id="prof-summary" rows={4} {...form.register("professional_summary")} />
          <EvidenceCaption quote={form.watch("summary_evidence_quote")} verified />
        </CardContent>
      </Card>

      {/* Experiências Profissionais */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Experiências profissionais</CardTitle>
            <CardDescription>Cargos, empresas, períodos e responsabilidades reais.</CardDescription>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              experiences.append({
                role: "",
                company: "",
                period: "",
                location: "",
                responsibilities: [],
                achievements: [],
                evidence_quote: "Adicionado manualmente pelo usuário na revisão.",
                evidence_verified: true,
              })
            }
          >
            <Plus /> Adicionar experiência
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {experiences.fields.length === 0 && (
            <p className="text-muted-foreground text-sm">Nenhuma experiência identificada.</p>
          )}
          {experiences.fields.map((field, idx) => (
            <div key={field.id} className="rounded-lg border p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold">Experiência #{idx + 1}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remover experiência ${idx + 1}`}
                  onClick={() => experiences.remove(idx)}
                >
                  <Trash2 />
                </Button>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`exp-role-${idx}`}>Cargo *</Label>
                  <Input id={`exp-role-${idx}`} {...form.register(`experiences.${idx}.role`)} />
                  {errors.experiences?.[idx]?.role && (
                    <p className="text-destructive text-xs">{errors.experiences[idx]?.role?.message}</p>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`exp-company-${idx}`}>Empresa</Label>
                  <Input id={`exp-company-${idx}`} {...form.register(`experiences.${idx}.company`)} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`exp-period-${idx}`}>Período</Label>
                  <Input id={`exp-period-${idx}`} {...form.register(`experiences.${idx}.period`)} />
                </div>
              </div>
              <div className="mt-3 flex flex-col gap-1">
                <Label htmlFor={`exp-resp-${idx}`}>Responsabilidades (uma por linha)</Label>
                <Textarea
                  id={`exp-resp-${idx}`}
                  rows={3}
                  value={(form.watch(`experiences.${idx}.responsibilities`) || []).join("\n")}
                  onChange={(e) =>
                    form.setValue(
                      `experiences.${idx}.responsibilities`,
                      e.target.value
                        .split("\n")
                        .map((s) => s.trim())
                        .filter(Boolean),
                      { shouldDirty: true },
                    )
                  }
                />
              </div>
              <EvidenceCaption
                quote={form.watch(`experiences.${idx}.evidence_quote`)}
                verified={form.watch(`experiences.${idx}.evidence_verified`)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Formação Acadêmica */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Formação acadêmica</CardTitle>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              education.append({
                degree: "",
                institution: "",
                period: "",
                evidence_quote: "Adicionado manualmente pelo usuário na revisão.",
                evidence_verified: true,
              })
            }
          >
            <Plus /> Adicionar formação
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {education.fields.map((field, idx) => (
            <div key={field.id} className="rounded-lg border p-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`edu-degree-${idx}`}>Curso / Grau *</Label>
                  <Input id={`edu-degree-${idx}`} {...form.register(`education.${idx}.degree`)} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor={`edu-inst-${idx}`}>Instituição</Label>
                  <Input id={`edu-inst-${idx}`} {...form.register(`education.${idx}.institution`)} />
                </div>
                <div className="flex items-end gap-2">
                  <div className="flex flex-1 flex-col gap-1">
                    <Label htmlFor={`edu-period-${idx}`}>Período</Label>
                    <Input id={`edu-period-${idx}`} {...form.register(`education.${idx}.period`)} />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remover formação ${idx + 1}`}
                    onClick={() => education.remove(idx)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </div>
              <EvidenceCaption
                quote={form.watch(`education.${idx}.evidence_quote`)}
                verified={form.watch(`education.${idx}.evidence_verified`)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Competências Técnicas */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Competências técnicas</CardTitle>
            <CardDescription>Tecnologias, ferramentas e metodologias comprovadas no currículo.</CardDescription>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              skills.append({
                name: "",
                category: "Técnica",
                evidence_quote: "Adicionado manualmente pelo usuário na revisão.",
                evidence_verified: true,
              })
            }
          >
            <Plus /> Adicionar competência
          </Button>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {skills.fields.map((field, idx) => (
            <div key={field.id} className="flex flex-col gap-1 rounded-md border p-2.5">
              <div className="flex items-center gap-1.5">
                <Input
                  aria-label={`Competência ${idx + 1}`}
                  placeholder="Ex.: Python"
                  {...form.register(`technical_skills.${idx}.name`)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remover competência ${idx + 1}`}
                  onClick={() => skills.remove(idx)}
                >
                  <Trash2 />
                </Button>
              </div>
              {form.watch(`technical_skills.${idx}.evidence_verified`) === false && (
                <span className="text-xs text-amber-700">Sem evidência literal no texto original</span>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Certificações, Idiomas e Projetos */}
      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Certificações</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                certifications.append({
                  name: "",
                  issuer: "",
                  year: "",
                  evidence_quote: "Adicionado manualmente.",
                  evidence_verified: true,
                })
              }
            >
              <Plus />
            </Button>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {certifications.fields.map((f, idx) => (
              <div key={f.id} className="flex items-center gap-1.5">
                <Input
                  aria-label={`Certificação ${idx + 1}`}
                  placeholder="Certificação"
                  {...form.register(`certifications.${idx}.name`)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => certifications.remove(idx)}
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Idiomas</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                languages.append({
                  language: "",
                  proficiency: "",
                  evidence_quote: "Adicionado manualmente.",
                  evidence_verified: true,
                })
              }
            >
              <Plus />
            </Button>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {languages.fields.map((f, idx) => (
              <div key={f.id} className="flex items-center gap-1.5">
                <Input
                  aria-label={`Idioma ${idx + 1}`}
                  placeholder="Idioma"
                  {...form.register(`languages.${idx}.language`)}
                />
                <Input
                  aria-label={`Proficiência ${idx + 1}`}
                  placeholder="Nível"
                  {...form.register(`languages.${idx}.proficiency`)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => languages.remove(idx)}
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Projetos</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                projects.append({
                  name: "",
                  description: "",
                  technologies: [],
                  url: "",
                  evidence_quote: "Adicionado manualmente.",
                  evidence_verified: true,
                })
              }
            >
              <Plus />
            </Button>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {projects.fields.map((f, idx) => (
              <div key={f.id} className="flex items-center gap-1.5">
                <Input
                  aria-label={`Projeto ${idx + 1}`}
                  placeholder="Nome do projeto"
                  {...form.register(`projects.${idx}.name`)}
                />
                <Button type="button" variant="ghost" size="icon" onClick={() => projects.remove(idx)}>
                  <Trash2 />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Separator />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-muted-foreground text-xs">
          Nenhuma informação é usada na geração de currículos ATS sem a sua confirmação explícita.
        </p>
        <Button type="submit" size="lg" disabled={isSaving}>
          <CheckCircle2 />
          {isSaving ? "Salvando…" : "Confirmar dados do currículo"}
        </Button>
      </div>
    </form>
  );
}
