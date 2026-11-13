import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { ResumeUploadCard } from "@/components/resume/ResumeUploadCard";
import { ResumeReviewForm } from "@/components/resume/ResumeReviewForm";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useConfirmResume,
  useCurrentResume,
  useParseResume,
  useUploadResume,
} from "@/hooks/useResume";
import type { ParsedResumeData } from "@/types/resume";

export default function ResumePage() {
  const { data: state, isLoading } = useCurrentResume();
  const uploadMutation = useUploadResume();
  const parseMutation = useParseResume();
  const confirmMutation = useConfirmResume();
  const [actionError, setActionError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleSelectFile = async (file: File) => {
    setActionError(null);
    try {
      setStatusMessage("Extraindo texto do documento com segurança…");
      const uploaded = await uploadMutation.mutateAsync(file);
      setStatusMessage("Estruturando informações e validando evidências do currículo…");
      const parsed = await parseMutation.mutateAsync({ text: uploaded.raw_text });
      setStatusMessage(null);
      if (parsed.extraction_method === "deterministic_fallback") {
        toast.info("Currículo extraído no modo determinístico local. Revise os campos abaixo.");
      } else {
        toast.success("Currículo analisado com sucesso! Revise e confirme os dados.");
      }
    } catch (err) {
      setStatusMessage(null);
      const msg = err instanceof Error ? err.message : "Falha ao processar o arquivo enviado.";
      setActionError(msg);
      toast.error(msg);
    }
  };

  const handleSubmitText = async (text: string) => {
    setActionError(null);
    try {
      setStatusMessage("Estruturando informações e validando evidências do currículo…");
      const parsed = await parseMutation.mutateAsync({ text });
      setStatusMessage(null);
      if (parsed.extraction_method === "deterministic_fallback") {
        toast.info("Currículo estruturado no modo determinístico local. Revise os campos abaixo.");
      } else {
        toast.success("Currículo estruturado com sucesso! Revise e confirme os dados.");
      }
    } catch (err) {
      setStatusMessage(null);
      const msg = err instanceof Error ? err.message : "Falha ao analisar o texto do currículo.";
      setActionError(msg);
      toast.error(msg);
    }
  };

  const handleConfirm = async (values: ParsedResumeData) => {
    setActionError(null);
    try {
      await confirmMutation.mutateAsync({ data: values, confirmed: true });
      toast.success("Dados do currículo confirmados com sucesso!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Não foi possível salvar a confirmação.";
      setActionError(msg);
      toast.error(msg);
    }
  };

  const isBusy = uploadMutation.isPending || parseMutation.isPending;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Currículo"
        description="Envie seu documento (PDF, DOCX ou TXT) ou cole o texto, revise as evidências extraídas e confirme suas informações."
        actions={
          state?.confirmed ? (
            <Button asChild variant="accent">
              <Link to="/vaga">
                <CheckCircle2 /> Avançar para Vaga <ArrowRight />
              </Link>
            </Button>
          ) : undefined
        }
      />

      <ResumeUploadCard
        initialText={state?.raw_text ?? ""}
        isBusy={isBusy}
        statusMessage={statusMessage}
        errorMessage={actionError}
        onSelectFile={handleSelectFile}
        onSubmitText={handleSubmitText}
      />

      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {state?.data && (
        <section aria-label="Revisão estruturada do currículo">
          <ResumeReviewForm
            data={state.data}
            extractionMethod={state.extraction_method}
            providerUsed={state.provider_used}
            fallbackReason={state.provider_fallback_reason}
            evidenceReport={state.evidence_report}
            confirmed={state.confirmed}
            isSaving={confirmMutation.isPending}
            onConfirm={handleConfirm}
          />
        </section>
      )}
    </div>
  );
}
