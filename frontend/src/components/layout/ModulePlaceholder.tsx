import { Link } from "react-router-dom";
import { Construction } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Honest placeholder for modules that will be delivered in later roadmap phases.
 * It never shows fake data.
 */
export function ModulePlaceholder({
  title,
  description,
  phase,
  features,
}: {
  title: string;
  description: string;
  phase: number;
  features: string[];
}) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <Card>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Construction className="text-amber-600 size-6" aria-hidden />
            <p className="font-medium">Módulo em desenvolvimento (Fase {phase} do roadmap).</p>
          </div>
          <ul className="text-muted-foreground list-disc space-y-1 pl-6 text-sm">
            {features.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <Button variant="outline" asChild className="w-fit">
            <Link to="/">Voltar ao início</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
