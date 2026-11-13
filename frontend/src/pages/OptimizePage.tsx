import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  HelpCircle,
  Loader2,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useATSResume } from "@/hooks/useATSResume";
import { getATSExportUrl } from "@/services/atsResumeService";
import type { ExportFormat } from "@/types/atsResume";

export function OptimizePage() {
  const {
    result,
    resumeConfirmed,
    jobConfirmed,
    isLoadingStatus,
    isGenerating,
    isSaving,
    error,
    successMessage,
    generate,
    saveAndApprove,
  } = useATSResume();

  const [useDeterministicOnly, setUseDeterministicOnly] = useState(false);
  const [editedSummary, setEditedSummary] = useState("");
  const [editedSkillsText, setEditedSkillsText] = useState("");

  useEffect(() => {
    if (result?.optimized_data) {
      setEditedSummary(result.optimized_data.professional_summary ?? "");
      setEditedSkillsText(
        result.optimized_data.technical_skills.map((s) => s.name).join(", "),
      );
    }
  }, [result]);

  const canRun = resumeConfirmed && jobConfirmed && !isLoadingStatus;

  const handleApprove = async () => {
    if (!result) return;
    const updatedSkills = editedSkillsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((name) => {
        const existing = result.optimized_data.technical_skills.find(
          (sk) => sk.name.toLowerCase() === name.toLowerCase(),
        );
        return (
          existing ?? {
            name,
            category: "Técnica",
            evidence_quote: name,
            evidence_verified: true,
          }
        );
      });

    await saveAndApprove(
      {
        ...result.optimized_data,
        professional_summary: editedSummary.trim(),
        technical_skills: updatedSkills,
      },
      true,
    );
  };

  const exportFormats: { fmt: ExportFormat; label: string }[] = [
    { fmt: "pdf", label: "Exportar PDF (ATS)" },
    { fmt: "docx", label: "Exportar DOCX (Word)" },
    { fmt: "txt", label: "Exportar TXT" },
    { fmt: "md", label: "Exportar Markdown" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Badge variant="secondary" className="mb-2">
            Fase 5 • Currículo ATS Friendly
          </Badge>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Geração e Otimização de Currículo ATS
          </h1>
          <p className="text-sm text-muted-foreground">
            Adapte seu currículo aos requisitos da vaga preservando 100% dos fatos reais, revise as
            justificativas e aprove para exportar em PDF ou DOCX.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={useDeterministicOnly}
              onChange={(e) => setUseDeterministicOnly(e.target.checked)}
              className="rounded border-input"
            />
            Apenas modo determinístico (sem LLM)
          </label>
          <Button
            onClick={() => void generate(useDeterministicOnly)}
            disabled={!canRun || isGenerating}
          >
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Gerando versão ATS...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 size-4" />
                {result ? "Regerar Currículo ATS" : "Gerar Currículo ATS"}
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Checklist de pré-requisitos */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className={resumeConfirmed ? "border-emerald-500/40" : "border-amber-500/40"}>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-base">
              <span>1. Currículo Confirmado</span>
              {resumeConfirmed ? (
                <Badge className="bg-emerald-600 text-white">Confirmado</Badge>
              ) : (
                <Badge variant="outline" className="border-amber-500 text-amber-700">
                  Pendente
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              {resumeConfirmed
                ? "Dados originais verificados e prontos para otimização."
                : "Envie e confirme seu currículo antes de gerar a versão ATS."}
            </CardDescription>
          </CardHeader>
          {!resumeConfirmed && (
            <CardContent>
              <Button asChild variant="outline" size="sm">
                <Link to="/curriculo">Ir para /curriculo</Link>
              </Button>
            </CardContent>
          )}
        </Card>

        <Card className={jobConfirmed ? "border-emerald-500/40" : "border-amber-500/40"}>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-base">
              <span>2. Vaga Confirmada</span>
              {jobConfirmed ? (
                <Badge className="bg-emerald-600 text-white">Confirmada</Badge>
              ) : (
                <Badge variant="outline" className="border-amber-500 text-amber-700">
                  Pendente
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              {jobConfirmed
                ? "Requisitos da vaga prontos para alinhamento ATS."
                : "Analise e confirme os requisitos da vaga antes de gerar a versão ATS."}
            </CardDescription>
          </CardHeader>
          {!jobConfirmed && (
            <CardContent>
              <Button asChild variant="outline" size="sm">
                <Link to="/vaga">Ir para /vaga</Link>
              </Button>
            </CardContent>
          )}
        </Card>
      </div>

      {!canRun && !isLoadingStatus && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-300"
        >
          <AlertCircle className="size-4 shrink-0" />
          <span>
            Confirme o currículo e a vaga antes de gerar o currículo ATS otimizado.
          </span>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <AlertCircle className="size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMessage && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-800 dark:text-emerald-300"
        >
          <CheckCircle2 className="size-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Selo de Preservação de Dados (Zero Fabricação) */}
          <Card className="border-emerald-500/40 bg-emerald-500/5">
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-base text-emerald-800 dark:text-emerald-300">
                  <ShieldCheck className="size-5" />
                  Garantia Anti-Alucinação: Preservação Factual Verificada
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">
                    Modo: {result.optimization_method} ({result.provider_used})
                  </Badge>
                  {result.approved ? (
                    <Badge className="bg-emerald-600 text-white" data-testid="approval-badge">
                      Aprovado pelo usuário
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="border-amber-500 text-amber-700">
                      Aguardando aprovação humana
                    </Badge>
                  )}
                </div>
              </div>
              <CardDescription className="text-emerald-900/80 dark:text-emerald-200/80">
                {result.preservation_report.verification_note}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <div className="flex flex-wrap gap-4">
                <span>
                  Experiências preservadas:{" "}
                  <strong>{result.preservation_report.preserved_experiences_count}</strong>
                </span>
                <span>
                  Competências comprovadas:{" "}
                  <strong>{result.preservation_report.preserved_skills_count}</strong>
                </span>
                <span>
                  Formações preservadas:{" "}
                  <strong>{result.preservation_report.preserved_education_count}</strong>
                </span>
                <span>
                  Certificações preservadas:{" "}
                  <strong>{result.preservation_report.preserved_certifications_count}</strong>
                </span>
              </div>
              {result.provider_fallback_reason && (
                <p className="text-amber-700 dark:text-amber-300">
                  Nota de transparência: {result.provider_fallback_reason}
                </p>
              )}
              {result.preservation_report.blocked_fabrications.length > 0 && (
                <div className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-amber-800 dark:text-amber-300">
                  <strong>Itens bloqueados pelo guardião determinístico:</strong>
                  <ul className="list-disc pl-5">
                    {result.preservation_report.blocked_fabrications.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Palavras-chave incorporadas vs. Sugestões consultivas */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  Palavras-Chave Comprovadas e Destacadas
                </CardTitle>
                <CardDescription>
                  Competências da vaga já comprovadas no seu currículo original e priorizadas na
                  estrutura ATS.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {result.incorporated_keywords.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Nenhuma palavra-chave direta identificada.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {result.incorporated_keywords.map((kw, i) => (
                      <Badge
                        key={i}
                        variant="outline"
                        className="border-emerald-500/50 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
                      >
                        {kw}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <HelpCircle className="size-4 text-sky-600" />
                  Sugestões de Palavras-Chave (Não Adicionadas Automaticamente)
                </CardTitle>
                <CardDescription>
                  Termos da vaga sem evidência no seu currículo. Inclua manualmente apenas se você
                  tiver experiência real.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {result.suggested_keywords.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Todas as palavras-chave da vaga já foram contempladas!
                  </p>
                ) : (
                  <ul className="space-y-2 text-xs">
                    {result.suggested_keywords.map((sg, i) => (
                      <li key={i} className="rounded border p-2">
                        <div className="flex items-center justify-between gap-2 font-medium">
                          <span>{sg.keyword}</span>
                          <Badge variant="secondary" className="text-[10px]">
                            {sg.importance}
                          </Badge>
                        </div>
                        <p className="mt-1 text-muted-foreground">{sg.advisory_note}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Alterações realizadas e justificativas */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Alterações Realizadas e Justificativas ({result.changes.length})
              </CardTitle>
              <CardDescription>
                Rastreabilidade completa entre o currículo original e a versão otimizada para ATS.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {result.changes.map((ch, idx) => (
                <div key={idx} className="rounded-lg border p-3 text-sm space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">{ch.section}</span>
                    <Badge variant="outline">{ch.change_type}</Badge>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2 text-xs">
                    <div className="rounded bg-muted/50 p-2">
                      <span className="font-medium text-muted-foreground">Antes: </span>
                      <span>{ch.before}</span>
                    </div>
                    <div className="rounded bg-emerald-500/5 border border-emerald-500/20 p-2">
                      <span className="font-medium text-emerald-700 dark:text-emerald-300">
                        Depois:{" "}
                      </span>
                      <span>{ch.after}</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    <strong>Justificativa:</strong> {ch.justification}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Edição Humana e Pré-visualização ATS */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileCheck2 className="size-4" />
                  Revisão e Aprovação Humana
                </CardTitle>
                <CardDescription>
                  Ajuste o resumo profissional ou a lista de competências antes de aprovar o
                  documento para exportação.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="ats-summary" className="text-xs font-medium">
                    Resumo Profissional Otimizado
                  </label>
                  <Textarea
                    id="ats-summary"
                    rows={5}
                    value={editedSummary}
                    onChange={(e) => setEditedSummary(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="ats-skills" className="text-xs font-medium">
                    Competências Técnicas (separadas por vírgula, ordenadas por relevância ATS)
                  </label>
                  <Textarea
                    id="ats-skills"
                    rows={3}
                    value={editedSkillsText}
                    onChange={(e) => setEditedSkillsText(e.target.value)}
                  />
                </div>
                <Button
                  onClick={() => void handleApprove()}
                  disabled={isSaving}
                  className="w-full"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Salvando aprovação...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="mr-2 size-4" />
                      Aprovar Currículo Otimizado para Exportação
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="size-4" />
                  Pré-visualização Linear ATS (Coluna Única)
                </CardTitle>
                <CardDescription>
                  Estrutura limpa sem tabelas ou colunas, garantindo 100% de leitura por sistemas
                  ATS.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <pre
                  data-testid="ats-plain-preview"
                  className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 font-mono text-xs"
                >
                  {result.plain_text_preview}
                </pre>

                <div className="space-y-2">
                  <p className="text-xs font-medium">
                    Exportar Currículo Otimizado{" "}
                    {!result.approved && "(Aprove o currículo ao lado para liberar o download)"}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {exportFormats.map(({ fmt, label }) =>
                      result.approved ? (
                        <Button key={fmt} asChild variant="outline" size="sm">
                          <a href={getATSExportUrl(fmt)} download={`curriculo-ats.${fmt}`}>
                            <Download className="mr-1.5 size-3.5" />
                            {label}
                          </a>
                        </Button>
                      ) : (
                        <Button key={fmt} variant="outline" size="sm" disabled>
                          <Download className="mr-1.5 size-3.5" />
                          {label}
                        </Button>
                      ),
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
