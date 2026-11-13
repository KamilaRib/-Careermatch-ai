import { Link } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  HelpCircle,
  Info,
  Loader2,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentResume } from "@/hooks/useResume";
import { useCurrentJob } from "@/hooks/useJob";
import { useAnalyzeMatching, useCurrentMatching } from "@/hooks/useMatching";
import type { MatchState } from "@/types/matching";

function ScoreCircle({ score, bandLabel }: { score: number; bandLabel: string }) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference - (clamped / 100) * circumference;

  const strokeColor =
    clamped >= 80
      ? "#22C55E"
      : clamped >= 60
        ? "#60A5FA"
        : clamped >= 40
          ? "#F59E0B"
          : "#EF4444";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative flex size-36 items-center justify-center">
        <svg className="size-36 -rotate-90" viewBox="0 0 140 140" aria-hidden>
          <circle cx="70" cy="70" r={radius} stroke="#E2E8F0" strokeWidth="12" fill="none" />
          <circle
            cx="70"
            cy="70"
            r={radius}
            stroke={strokeColor}
            strokeWidth="12"
            strokeLinecap="round"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-3xl font-bold tracking-tight" data-testid="overall-score">
            {clamped}%
          </span>
          <span className="text-muted-foreground text-xs">Score ATS</span>
        </div>
      </div>
      <Badge variant={clamped >= 60 ? "success" : clamped >= 40 ? "accent" : "destructive"}>
        {bandLabel}
      </Badge>
    </div>
  );
}

function StateBadge({ state }: { state: MatchState }) {
  switch (state) {
    case "atendido":
      return (
        <Badge variant="success">
          <CheckCircle2 /> Atendido
        </Badge>
      );
    case "parcialmente_atendido":
      return (
        <Badge variant="accent">
          <AlertTriangle /> Parcialmente atendido
        </Badge>
      );
    case "nao_identificado":
      return (
        <Badge variant="secondary">
          <HelpCircle /> Não identificado no currículo
        </Badge>
      );
    case "nao_atendido":
      return (
        <Badge variant="destructive">
          <XCircle /> Não atendido
        </Badge>
      );
    default:
      return (
        <Badge variant="outline">
          <Info /> Não avaliável
        </Badge>
      );
  }
}

export default function MatchPage() {
  const { data: resumeState, isLoading: loadingResume } = useCurrentResume();
  const { data: jobState, isLoading: loadingJob } = useCurrentJob();
  const { data: matchResult, isLoading: loadingMatch } = useCurrentMatching();
  const analyzeMutation = useAnalyzeMatching();

  const readyToAnalyze = Boolean(resumeState?.confirmed && jobState?.confirmed);

  const handleAnalyze = async () => {
    try {
      await analyzeMutation.mutateAsync();
      toast.success("Análise de compatibilidade concluída!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao calcular compatibilidade.";
      toast.error(msg);
    }
  };

  const chartData =
    matchResult?.category_scores
      .filter((c) => c.applicable)
      .map((c) => ({
        name: c.label,
        score: c.score,
        peso: c.normalized_weight_pct,
      })) ?? [];

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Compatibilidade"
        description="Comparação determinística e transparente entre o seu currículo confirmado e os requisitos da vaga."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={handleAnalyze}
              disabled={!readyToAnalyze || analyzeMutation.isPending}
            >
              {analyzeMutation.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              {matchResult ? "Recalcular compatibilidade" : "Calcular compatibilidade"}
            </Button>
            {matchResult && (
              <Button variant="accent" asChild>
                <Link to="/curriculo-ats">
                  <Sparkles /> Gerar currículo otimizado para esta vaga <ArrowRight />
                </Link>
              </Button>
            )}
          </div>
        }
      />

      {/* Readiness Checklist */}
      {!readyToAnalyze && !loadingResume && !loadingJob && (
        <Card className="border-amber-300 bg-amber-50/70">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertCircle className="size-5 text-amber-700" aria-hidden />
              Confirme o currículo e a vaga antes de iniciar o matching
            </CardTitle>
            <CardDescription>
              Para garantir zero fabricação de dados e cálculo fiel, ambos os documentos precisam ser revisados e
              confirmados na sessão atual.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button variant={resumeState?.confirmed ? "secondary" : "default"} asChild>
              <Link to="/curriculo">
                {resumeState?.confirmed ? "✓ Currículo confirmado" : "1. Revisar e confirmar currículo"}
              </Link>
            </Button>
            <Button variant={jobState?.confirmed ? "secondary" : "default"} asChild>
              <Link to="/vaga">
                {jobState?.confirmed ? "✓ Vaga confirmada" : "2. Revisar e confirmar vaga"}
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {(loadingResume || loadingJob || loadingMatch) && <Skeleton className="h-64 w-full" />}

      {matchResult && (
        <>
          {/* Eliminatory Alerts */}
          {matchResult.eliminatory_alerts.length > 0 && (
            <div
              role="alert"
              className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-950"
            >
              <p className="font-semibold">Atenção — Requisitos eliminatórios da vaga:</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {matchResult.eliminatory_alerts.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Top Summary: Circular Score + Category Breakdown Chart */}
          <div className="grid gap-6 lg:grid-cols-12">
            <Card className="lg:col-span-4">
              <CardHeader>
                <CardTitle>Score Estimado</CardTitle>
                <CardDescription>Estimativa interna (0 a 100), não probabilidade de contratação.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col items-center gap-4">
                <ScoreCircle score={matchResult.overall_score} bandLabel={matchResult.band_label} />
                <p className="text-muted-foreground text-center text-xs leading-relaxed">
                  {matchResult.methodology_note}
                </p>
              </CardContent>
            </Card>

            <Card className="lg:col-span-8">
              <CardHeader>
                <CardTitle>Desempenho por categoria</CardTitle>
                <CardDescription>
                  Pontuação por dimensão e pesos normalizados aplicados nesta análise.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="h-56 w-full" aria-label="Gráfico de pontuação por categoria">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: 16, right: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" domain={[0, 100]} unit="%" />
                      <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12 }} />
                      <RechartsTooltip />
                      <Bar dataKey="score" fill="#60A5FA" radius={[0, 6, 6, 0]} name="Score (%)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {matchResult.category_scores
                    .filter((c) => c.applicable)
                    .map((cat) => (
                      <div key={cat.key} className="rounded-lg border p-3">
                        <div className="mb-1.5 flex items-center justify-between text-xs font-medium">
                          <span>{cat.label}</span>
                          <span>
                            {cat.score}% (peso {cat.normalized_weight_pct}%)
                          </span>
                        </div>
                        <Progress value={cat.score} />
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Keywords & Gaps Summary Cards */}
          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Competências correspondentes</CardTitle>
                <CardDescription>Comprovadas diretamente no currículo</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {matchResult.matched_keywords.length === 0 ? (
                  <span className="text-muted-foreground text-sm">Nenhuma identificada ainda.</span>
                ) : (
                  matchResult.matched_keywords.map((kw) => (
                    <Badge key={kw} variant="success">
                      {kw}
                    </Badge>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Parcialmente correspondentes</CardTitle>
                <CardDescription>Tecnologia correlata ou atendimento parcial</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {matchResult.partial_keywords.length === 0 ? (
                  <span className="text-muted-foreground text-sm">Nenhuma correspondência parcial.</span>
                ) : (
                  matchResult.partial_keywords.map((kw) => (
                    <Badge key={kw} variant="accent">
                      {kw}
                    </Badge>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Requisitos não comprovados</CardTitle>
                <CardDescription>Ausentes no texto do currículo atual</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {matchResult.unverified_requirements.length === 0 ? (
                  <span className="text-muted-foreground text-sm">Todos os requisitos foram comprovados!</span>
                ) : (
                  matchResult.unverified_requirements.map((kw) => (
                    <Badge key={kw} variant="secondary">
                      {kw}
                    </Badge>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          {/* Detailed Requirement Matrix with Evidences */}
          <Card>
            <CardHeader>
              <CardTitle>Análise detalhada de requisitos e evidências</CardTitle>
              <CardDescription>
                Justificativa individual de cada requisito da vaga cruzado com o texto do seu currículo.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {matchResult.requirement_matches.map((rm) => (
                <div key={rm.requirement_name} className="rounded-lg border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{rm.requirement_name}</span>
                      <Badge variant="outline">{rm.importance}</Badge>
                      {rm.is_eliminatory && <Badge variant="destructive">Eliminatório</Badge>}
                    </div>
                    <StateBadge state={rm.state} />
                  </div>
                  <p className="text-muted-foreground mt-2 text-sm">{rm.explanation}</p>
                  {rm.resume_evidence && (
                    <p className="bg-muted/60 mt-2 rounded border px-3 py-1.5 text-xs">
                      <strong>Evidência no currículo:</strong> {rm.resume_evidence}
                    </p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Strengths, Gaps & Recommendations */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Pontos fortes e lacunas</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div>
                  <p className="font-semibold text-green-800">Pontos fortes comprovados</p>
                  <ul className="text-muted-foreground mt-1 list-disc space-y-1 pl-5">
                    {matchResult.strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
                {matchResult.gaps.length > 0 && (
                  <div>
                    <p className="font-semibold text-amber-900">Lacunas / Requisitos sem evidência no currículo</p>
                    <ul className="text-muted-foreground mt-1 list-disc space-y-1 pl-5">
                      {matchResult.gaps.map((g) => (
                        <li key={g}>{g}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recomendações de melhoria</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col justify-between gap-4">
                <ul className="text-muted-foreground list-disc space-y-2 pl-5 text-sm">
                  {matchResult.recommendations.map((rec) => (
                    <li key={rec}>{rec}</li>
                  ))}
                </ul>
                <Button variant="accent" size="lg" asChild className="w-full">
                  <Link to="/curriculo-ats">
                    <Sparkles /> Gerar currículo otimizado para esta vaga
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
