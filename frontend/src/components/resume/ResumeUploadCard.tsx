import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { AlertCircle, FileText, Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const MAX_MB = 10;
const ALLOWED_EXT = [".pdf", ".docx", ".txt"];

interface ResumeUploadCardProps {
  initialText?: string;
  isBusy: boolean;
  statusMessage?: string | null;
  errorMessage?: string | null;
  onSelectFile: (file: File) => void;
  onSubmitText: (text: string) => void;
}

export function ResumeUploadCard({
  initialText = "",
  isBusy,
  statusMessage,
  errorMessage,
  onSelectFile,
  onSubmitText,
}: ResumeUploadCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pastedText, setPastedText] = useState(initialText);
  const [clientError, setClientError] = useState<string | null>(null);

  const validateAndForward = (file: File) => {
    setClientError(null);
    const lower = file.name.toLowerCase();
    if (!ALLOWED_EXT.some((ext) => lower.endsWith(ext))) {
      setClientError("Formato não suportado. Envie um arquivo PDF, DOCX ou TXT.");
      return;
    }
    if (file.size === 0) {
      setClientError("O arquivo selecionado está vazio.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setClientError(`O arquivo excede o limite de ${MAX_MB} MB.`);
      return;
    }
    onSelectFile(file);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (isBusy) return;
    const file = e.dataTransfer.files?.[0];
    if (file) validateAndForward(file);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndForward(file);
    e.target.value = "";
  };

  const handlePasteSubmit = () => {
    setClientError(null);
    const trimmed = pastedText.trim();
    if (trimmed.length < 30) {
      setClientError("Cole pelo menos 30 caracteres do seu currículo para iniciar a análise.");
      return;
    }
    onSubmitText(trimmed);
  };

  const displayedError = clientError || errorMessage;

  return (
    <Card>
      <CardHeader>
        <CardTitle>1. Envie seu currículo ou cole o texto</CardTitle>
        <CardDescription>
          Aceitamos arquivos PDF (com texto selecionável), DOCX ou TXT até {MAX_MB} MB. O arquivo original é processado
          em memória e descartado imediatamente após a extração.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Tabs defaultValue="upload">
          <TabsList>
            <TabsTrigger value="upload">Upload de arquivo</TabsTrigger>
            <TabsTrigger value="paste">Colar texto</TabsTrigger>
          </TabsList>

          <TabsContent value="upload">
            <div
              role="region"
              aria-label="Área de upload de currículo"
              onDragOver={(e) => {
                e.preventDefault();
                if (!isBusy) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              className={cn(
                "border-border bg-muted/40 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 text-center transition-colors",
                dragging && "border-primary bg-primary-soft/50",
                isBusy && "opacity-60",
              )}
            >
              <Upload className="text-primary-strong size-8" aria-hidden />
              <div>
                <p className="font-medium">Arraste e solte seu currículo aqui</p>
                <p className="text-muted-foreground text-xs">PDF, DOCX ou TXT · Máximo de {MAX_MB} MB</p>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                className="sr-only"
                aria-label="Selecionar arquivo de currículo"
                onChange={handleFileChange}
                disabled={isBusy}
              />
              <Button
                type="button"
                variant="outline"
                disabled={isBusy}
                onClick={() => inputRef.current?.click()}
              >
                <FileText /> Selecionar arquivo
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="paste">
            <div className="flex flex-col gap-3">
              <Label htmlFor="resume-raw-textarea">Texto completo do currículo</Label>
              <Textarea
                id="resume-raw-textarea"
                rows={10}
                placeholder="Cole aqui o conteúdo do seu currículo (dados de contato, resumo, experiências, formação, competências)..."
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                disabled={isBusy}
              />
              <div className="flex justify-end">
                <Button type="button" onClick={handlePasteSubmit} disabled={isBusy}>
                  Estruturar currículo colado
                </Button>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {isBusy && (
          <div
            role="status"
            aria-live="polite"
            className="bg-secondary/60 text-foreground flex items-center gap-2.5 rounded-lg border px-4 py-3 text-sm"
          >
            <Loader2 className="size-4 animate-spin" aria-hidden />
            <span>{statusMessage || "Processando currículo…"}</span>
          </div>
        )}

        {displayedError && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900"
          >
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-600" aria-hidden />
            <span>{displayedError}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
