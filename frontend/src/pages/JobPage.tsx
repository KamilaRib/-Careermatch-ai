import { useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Globe,
  Loader2,
  Plus,
  Quote,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useConfirmJob,
  useCurrentJob,
  useExtractJobUrl,
  useParseJob,
} from "@/hooks/useJob";
import { parsedJobSchema, type ParsedJobFormValues } from "@/schemas/jobSchema";
import type { ParsedJobData } from "@/types/job";

const EMPTY_MANUAL_JOB: ParsedJobData = {
  title: "",
  company: "",
  location: "",
  work_model: "Remoto",
  seniority: "Sênior",
  experience_years_required: "",
  education_required: "",
  responsibilities: [],
  requirements: [
    {
      name: "",
      category: "competencias_tecnicas",
      importance: "obrigatorio",
      is_eliminatory: false,
      evidence_quote: "Preenchido manualmente pelo usuário.",
      evidence_verified: true,
    },
  ],
  technologies: [],
  languages: [],
  keywords: [],
};

export default function JobPage() {
  const { data: state, isLoading } = useCurrentJob();
  const parseMutation = useParseJob();
  const urlMutation = useExtractJobUrl();
  const confirmMutation = useConfirmJob();

  const [pastedText, setPastedText] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [manualMode, setManualMode] = useState(false);

  useEffect(() => {
    if (state?.raw_text && !pastedText) {
      setPastedText(state.raw_text);
    }
  }, [state?.raw_text, pastedText]);

  const activeData = state?.data ?? (manualMode ? EMPTY_MANUAL_JOB : null);

  const form = useForm<ParsedJobFormValues>({
    resolver: zodResolver(parsedJobSchema),
    defaultValues: activeData ?? EMPTY_MANUAL_JOB,
  });

  useEffect(() => {
    if (state?.data) {
      form.reset(state.data);
    }
  }, [state?.data, form]);

  const requirements = useFieldArray({ control: form.control, name: "requirements" });

  const handleParsePasted = async () => {
    setActionError(null);
    const trimmed = pastedText.trim();
    if (trimmed.length < 30) {
      setActionError("Cole pelo menos 30 caracteres da descrição da vaga.");
      return;
    }
    try {
      const res = await parseMutation.mutateAsync({ text: trimmed });
      if (res.extraction_method === "deterministic_fallback") {
        toast.info("Vaga estruturada no modo determinístico local. Revise os requisitos.");
      } else {
        toast.success("Vaga estruturada com sucesso!");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao analisar a descrição da vaga.";
      setActionError(msg);
      toast.error(msg);
    }
  };

  const handleExtractUrl = async () => {
    setActionError(null);
    const trimmed = urlInput.trim();
    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
      setActionError("Informe uma URL pública iniciada por http:// ou https://.");
      return;
    }
    try {
      const res = await urlMutation.mutateAsync({ url: trimmed });
      setPastedText(res.raw_text);
      toast.success("Texto extraído da URL e estruturado com sucesso!");
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Não foi possível extrair a URL. Cole a descrição da vaga manualmente.";
      setActionError(msg);
      toast.error(msg);
    }
  };

  const handleStartManual = () => {
    setActionError(null);
    setManualMode(true);
    form.reset(EMPTY_MANUAL_JOB);
  };

  const handleConfirm = async (values: ParsedJobFormValues) => {
    setActionError(null);
    try {
      await confirmMutation.mutateAsync({
        data: values,
        confirmed: true,
        raw_text: pastedText || state?.raw_text,
      });
      toast.success("Requisitos da vaga confirmados!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao confirmar a vaga.";
      setActionError(msg);
      toast.error(msg);
    }
  };

  const isBusy = parseMutation.isPending || urlMutation.isPending;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Vaga"
        description="Cole a descrição da vaga, extraia de uma URL pública segura ou preencha os requisitos manualmente."
        actions={
          state?.confirmed ? (
            <Button asChild variant="accent">
              <Link to="/compatibilidade">
                <CheckCircle2 /> Calcular Compatibilidade <ArrowRight />
              </Link>
            </Button>
          ) : undefined
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>1. Entrada da oportunidade</CardTitle>
          <CardDescription>
            Descrições de vagas são tratadas como conteúdo externo não confiável e validadas contra o texto original.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Tabs defaultValue="paste">
            <TabsList>
              <TabsTrigger value="paste">Colar descrição</TabsTrigger>
              <TabsTrigger value="url">Extrair de URL pública</TabsTrigger>
              <TabsTrigger value="manual" onClick={handleStartManual}>
                Preenchimento manual
              </TabsTrigger>
            </TabsList>

            <TabsContent value="paste">
              <div className="flex flex-col gap-3">
                <Label htmlFor="job-raw-textarea">Descrição completa da vaga</Label>
                <Textarea
                  id="job-raw-textarea"
                  rows={9}
                  placeholder="Cole aqui o título do cargo, responsabilidades, requisitos obrigatórios e diferenciais..."
                  value={pastedText}
                  onChange={(e) => setPastedText(e.target.value)}
                  disabled={isBusy}
                />
                <div className="flex justify-end">
                  <Button type="button" onClick={handleParsePasted} disabled={isBusy}>
                    Estruturar requisitos da vaga
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="url">
              <div className="flex flex-col gap-3">
                <Label htmlFor="job-url-input">URL pública da vaga</Label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input
                    id="job-url-input"
                    type="url"
                    placeholder="https://empresa.com/carreiras/vaga-backend"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    disabled={isBusy}
                  />
                  <Button type="button" onClick={handleExtractUrl} disabled={isBusy}>
                    <Globe /> Extrair da URL
                  </Button>
                </div>
                <p className="text-muted-foreground text-xs">
                  A extração ocorre exclusivamente no backend com proteção contra SSRF. Caso o site exija login ou
                  CAPTCHA, cole a descrição na aba anterior.
                </p>
              </div>
            </TabsContent>

            <TabsContent value="manual">
              <p className="text-muted-foreground text-sm">
                Preencha ou edite diretamente os campos estruturados abaixo e clique em{" "}
                <strong>Confirmar requisitos da vaga</strong>.
              </p>
            </TabsContent>
          </Tabs>

          {isBusy && (
            <div
              role="status"
              aria-live="polite"
              className="bg-secondary/60 flex items-center gap-2.5 rounded-lg border px-4 py-3 text-sm"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden />
              <span>Analisando vaga e classificando requisitos…</span>
            </div>
          )}

          {actionError && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900"
            >
              <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-600" aria-hidden />
              <span>{actionError}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {isLoading && <Skeleton className="h-64 w-full" />}

      {activeData && (
        <form
          onSubmit={form.handleSubmit(handleConfirm)}
          className="flex flex-col gap-6"
          aria-label="Revisão estruturada da vaga"
          noValidate
        >
          {state?.data && (
            <Card className="bg-secondary/40">
              <CardContent className="flex flex-wrap items-center gap-2">
                {state.extraction_method === "llm" ? (
                  <Badge variant="default">
                    <Sparkles /> Extraído por IA ({state.provider_used})
                  </Badge>
                ) : (
                  <Badge variant="accent">
                    <Cpu /> Extração determinística local (modo sem IA)
                  </Badge>
                )}
                <Badge variant="outline">
                  Evidências verificadas: {state.evidence_report.verified_items}/
                  {state.evidence_report.total_items_checked}
                </Badge>
                {state.confirmed && (
                  <Badge variant="success">
                    <ShieldCheck /> Vaga confirmada pelo usuário
                  </Badge>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Dados gerais da oportunidade</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label htmlFor="job-title">Cargo *</Label>
                <Input id="job-title" {...form.register("title")} />
                {form.formState.errors.title && (
                  <p className="text-destructive text-xs">{form.formState.errors.title.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="job-company">Empresa</Label>
                <Input id="job-company" {...form.register("company")} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="job-seniority">Senioridade</Label>
                <Input id="job-seniority" {...form.register("seniority")} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="job-work-model">Modalidade</Label>
                <Input id="job-work-model" {...form.register("work_model")} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="job-location">Localização</Label>
                <Input id="job-location" {...form.register("location")} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Requisitos classificados</CardTitle>
                <CardDescription>
                  Classifique cada requisito entre obrigatório, desejável, contextual ou não especificado.
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  requirements.append({
                    name: "",
                    category: "competencias_tecnicas",
                    importance: "obrigatorio",
                    is_eliminatory: false,
                    evidence_quote: "Adicionado manualmente pelo usuário.",
                    evidence_verified: true,
                  })
                }
              >
                <Plus /> Adicionar requisito
              </Button>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {requirements.fields.map((field, idx) => (
                <div key={field.id} className="rounded-lg border p-4">
                  <div className="grid gap-3 sm:grid-cols-12">
                    <div className="flex flex-col gap-1 sm:col-span-5">
                      <Label htmlFor={`req-name-${idx}`}>Requisito / Competência *</Label>
                      <Input id={`req-name-${idx}`} {...form.register(`requirements.${idx}.name`)} />
                    </div>
                    <div className="flex flex-col gap-1 sm:col-span-3">
                      <Label htmlFor={`req-cat-${idx}`}>Categoria</Label>
                      <select
                        id={`req-cat-${idx}`}
                        className="border-input bg-card h-9 rounded-md border px-2 text-sm"
                        {...form.register(`requirements.${idx}.category`)}
                      >
                        <option value="competencias_tecnicas">Competência técnica</option>
                        <option value="experiencia_profissional">Experiência profissional</option>
                        <option value="formacao_certificacoes">Formação / Certificação</option>
                        <option value="competencias_comportamentais">Comportamental</option>
                        <option value="idiomas">Idioma</option>
                        <option value="outros">Outros</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1 sm:col-span-3">
                      <Label htmlFor={`req-imp-${idx}`}>Nível de exigência</Label>
                      <select
                        id={`req-imp-${idx}`}
                        className="border-input bg-card h-9 rounded-md border px-2 text-sm"
                        {...form.register(`requirements.${idx}.importance`)}
                      >
                        <option value="obrigatorio">Obrigatório</option>
                        <option value="desejavel">Desejável</option>
                        <option value="contextual">Contextual</option>
                        <option value="nao_especificado">Não especificado</option>
                      </select>
                    </div>
                    <div className="flex items-end justify-end sm:col-span-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remover requisito ${idx + 1}`}
                        onClick={() => requirements.remove(idx)}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </div>
                  <div className="bg-muted/60 mt-2 flex items-center justify-between gap-2 rounded-md border px-3 py-1.5 text-xs">
                    <span className="text-muted-foreground flex items-center gap-1.5 truncate">
                      <Quote className="size-3 shrink-0" aria-hidden />
                      {form.watch(`requirements.${idx}.evidence_quote`) || "Sem citação literal."}
                    </span>
                    {form.watch(`requirements.${idx}.evidence_verified`) === false ? (
                      <Badge variant="accent">
                        <AlertTriangle /> Revisar
                      </Badge>
                    ) : (
                      <Badge variant="success">Verificado</Badge>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Separator />

          <div className="flex justify-end">
            <Button type="submit" size="lg" disabled={confirmMutation.isPending}>
              <CheckCircle2 />
              {confirmMutation.isPending ? "Salvando…" : "Confirmar requisitos da vaga"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
