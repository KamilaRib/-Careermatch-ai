import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Loader2,
  MessageSquarePlus,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
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
import { useAssistant } from "@/hooks/useAssistant";
import type { AssistantTopic } from "@/types/assistant";

const TOPIC_OPTIONS: { key: AssistantTopic; label: string }[] = [
  { key: "geral", label: "Visão Geral" },
  { key: "compatibilidade", label: "Compatibilidade" },
  { key: "lacunas", label: "Requisitos & Lacunas" },
  { key: "melhorias", label: "Melhorias no Currículo" },
  { key: "entrevista", label: "Entrevista" },
  { key: "candidatura", label: "Candidatura" },
];

export function AssistantPage() {
  const {
    history,
    contextSummary,
    suggestedPrompts,
    isLoadingState,
    isSending,
    error,
    sendMessage,
    clearHistory,
  } = useAssistant();

  const [input, setInput] = useState("");
  const [selectedTopic, setSelectedTopic] = useState<AssistantTopic>("geral");
  const [useDeterministicOnly, setUseDeterministicOnly] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isSending) return;
    const msg = input;
    setInput("");
    await sendMessage(msg, selectedTopic, useDeterministicOnly);
  };

  const handlePromptClick = async (promptText: string) => {
    if (isSending) return;
    await sendMessage(promptText, selectedTopic, useDeterministicOnly);
  };

  const hasFullContext = contextSummary.has_resume && contextSummary.has_job;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Badge variant="secondary" className="mb-2">
            Fase 6 • Assistente Contextual de Candidatura
          </Badge>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Assistente de Candidatura
          </h1>
          <p className="text-sm text-muted-foreground">
            Tire dúvidas sobre sua compatibilidade, lacunas técnicas, melhorias legítimas no
            currículo e preparação para entrevistas com base nos dados reais da sua sessão.
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
            Apenas modo determinístico (instantâneo)
          </label>
          {history.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void clearHistory()}
              disabled={isSending}
            >
              <Trash2 className="mr-1.5 size-3.5" />
              Limpar conversa
            </Button>
          )}
        </div>
      </div>

      {/* Painel de Contexto Ativo da Sessão */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-emerald-600" />
              Contexto Ativo da Sessão (Somente Leitura)
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              Score ATS imutável via chat
            </Badge>
          </div>
          <CardDescription>
            O assistente utiliza apenas evidências verificadas e nunca inventa qualificações nem
            altera o seu score determinístico.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border p-3 text-xs space-y-1">
              <div className="flex items-center justify-between font-medium">
                <span>Currículo</span>
                {contextSummary.has_resume ? (
                  <Badge className="bg-emerald-600 text-white text-[10px]">
                    {contextSummary.resume_confirmed ? "Confirmado" : "Carregado"}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-amber-500 text-amber-700 text-[10px]">
                    Ausente
                  </Badge>
                )}
              </div>
              <p className="text-muted-foreground truncate">
                {contextSummary.has_resume
                  ? `${contextSummary.candidate_name || "Candidato"} (${contextSummary.verified_skills.length} competências)`
                  : "Envie seu currículo em /curriculo"}
              </p>
            </div>

            <div className="rounded-lg border p-3 text-xs space-y-1">
              <div className="flex items-center justify-between font-medium">
                <span>Vaga Alvo</span>
                {contextSummary.has_job ? (
                  <Badge className="bg-emerald-600 text-white text-[10px]">
                    {contextSummary.job_confirmed ? "Confirmada" : "Carregada"}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-amber-500 text-amber-700 text-[10px]">
                    Ausente
                  </Badge>
                )}
              </div>
              <p className="text-muted-foreground truncate">
                {contextSummary.has_job
                  ? contextSummary.job_title || "Vaga estruturada"
                  : "Cadastre a vaga em /vaga"}
              </p>
            </div>

            <div className="rounded-lg border p-3 text-xs space-y-1">
              <div className="flex items-center justify-between font-medium">
                <span>Matching ATS</span>
                {contextSummary.has_matching && contextSummary.overall_score !== null ? (
                  <Badge
                    data-testid="assistant-context-score"
                    className="bg-primary text-primary-foreground text-[10px]"
                  >
                    {contextSummary.overall_score}%
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-[10px]">
                    Não calculado
                  </Badge>
                )}
              </div>
              <p className="text-muted-foreground truncate">
                {contextSummary.has_matching
                  ? contextSummary.band_label
                  : "Calcule em /compatibilidade"}
              </p>
            </div>
          </div>

          {!hasFullContext && !isLoadingState && (
            <div
              role="status"
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300"
            >
              <div className="flex items-center gap-2">
                <AlertCircle className="size-4 shrink-0" />
                <span>
                  Atenção: carregue e confirme seu currículo e a vaga para que o assistente possa
                  analisar evidências completas da sua candidatura.
                </span>
              </div>
              <div className="flex gap-2">
                {!contextSummary.has_resume && (
                  <Button asChild variant="outline" size="sm">
                    <Link to="/curriculo">Ir para /curriculo</Link>
                  </Button>
                )}
                {!contextSummary.has_job && (
                  <Button asChild variant="outline" size="sm">
                    <Link to="/vaga">Ir para /vaga</Link>
                  </Button>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Perguntas Rápidas Sugeridas */}
      {suggestedPrompts.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <MessageSquarePlus className="size-4 text-primary" />
              Perguntas Sugeridas
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {suggestedPrompts.map((promptText, idx) => (
              <Button
                key={idx}
                type="button"
                variant="outline"
                size="sm"
                className="h-auto whitespace-normal py-1.5 text-left text-xs"
                disabled={isSending}
                onClick={() => void handlePromptClick(promptText)}
              >
                <Sparkles className="mr-1.5 size-3 shrink-0 text-primary" />
                {promptText}
              </Button>
            ))}
          </CardContent>
        </Card>
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

      {/* Histórico de Mensagens */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Conversa com o Assistente</CardTitle>
          <CardDescription>
            Respostas fundamentadas com citações diretas aos dados verificados da sua sessão.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {history.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Nenhuma mensagem enviada ainda. Selecione uma pergunta sugerida acima ou escreva sua
              dúvida abaixo.
            </div>
          ) : (
            <div className="space-y-4" data-testid="assistant-chat-history">
              {history.map((msg) => (
                <div
                  key={msg.id}
                  className={`rounded-lg border p-4 text-sm space-y-2 ${
                    msg.role === "user"
                      ? "bg-muted/40 ml-4 sm:ml-12"
                      : "bg-card mr-4 sm:mr-12 border-primary/20"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1.5 font-semibold text-foreground">
                      {msg.role === "user" ? (
                        <>
                          <User className="size-3.5" />
                          Você
                        </>
                      ) : (
                        <>
                          <Bot className="size-3.5 text-primary" />
                          Assistente CareerMatch AI
                        </>
                      )}
                    </span>
                    {msg.role === "assistant" && msg.response_method && (
                      <Badge variant="secondary" className="text-[10px]">
                        Modo: {msg.response_method} ({msg.provider_used})
                      </Badge>
                    )}
                  </div>

                  <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                  {msg.provider_fallback_reason && (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      Nota de transparência: {msg.provider_fallback_reason}
                    </p>
                  )}

                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2 space-y-1.5 border-t pt-2 text-xs">
                      <p className="font-medium text-muted-foreground flex items-center gap-1">
                        <CheckCircle2 className="size-3 text-emerald-600" />
                        Referências aos dados da sessão:
                      </p>
                      <div className="grid gap-1.5 sm:grid-cols-2">
                        {msg.citations.map((cit, cIdx) => (
                          <div key={cIdx} className="rounded bg-muted/50 p-2">
                            <span className="font-semibold">[{cit.source.toUpperCase()}] </span>
                            <span className="font-medium">{cit.label}: </span>
                            <span className="text-muted-foreground">{cit.evidence}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Formulário de Envio */}
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3 border-t pt-4">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground mr-1">Foco:</span>
              {TOPIC_OPTIONS.map((opt) => (
                <Button
                  key={opt.key}
                  type="button"
                  size="sm"
                  variant={selectedTopic === opt.key ? "default" : "outline"}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setSelectedTopic(opt.key)}
                >
                  {opt.label}
                </Button>
              ))}
            </div>

            <div className="space-y-2">
              <label htmlFor="assistant-message-input" className="sr-only">
                Sua pergunta sobre a candidatura
              </label>
              <Textarea
                id="assistant-message-input"
                placeholder="Ex.: Como posso explicar na entrevista que tenho experiência em Docker e AWS, mas ainda não atuei com Kubernetes?"
                rows={3}
                maxLength={1500}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isSending}
              />
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {input.length}/1500 caracteres
              </span>
              <Button type="submit" disabled={isSending || input.trim().length < 2}>
                {isSending ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Consultando assistente...
                  </>
                ) : (
                  <>
                    <Send className="mr-2 size-4" />
                    Enviar Pergunta
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default AssistantPage;

