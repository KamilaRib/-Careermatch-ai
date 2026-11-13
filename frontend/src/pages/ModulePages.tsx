import { ModulePlaceholder } from "@/components/layout/ModulePlaceholder";

export function AssistantPage() {
  return (
    <ModulePlaceholder
      title="Career AI Assistant"
      description="Tire dúvidas sobre currículo, vaga, entrevistas e estratégia de candidatura."
      phase={6}
      features={["Chat contextual com os dados da sua sessão", "Sem compartilhamento entre sessões"]}
    />
  );
}
