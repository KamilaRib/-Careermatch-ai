import { ModulePlaceholder } from "@/components/layout/ModulePlaceholder";

export function ResumePage() {
  return (
    <ModulePlaceholder
      title="Currículo"
      description="Envie seu currículo em PDF, DOCX ou TXT, ou cole o texto."
      phase={2}
      features={[
        "Upload com arrastar e soltar (até 10 MB)",
        "Extração de texto real (PyMuPDF / python-docx)",
        "Estruturação por IA com evidências do texto original",
        "Formulário de revisão e confirmação",
      ]}
    />
  );
}

export function JobPage() {
  return (
    <ModulePlaceholder
      title="Vaga"
      description="Cole a descrição, informe uma URL pública ou preencha manualmente."
      phase={3}
      features={[
        "Classificação de requisitos: obrigatório, desejável ou contextual",
        "Extração segura por URL (proteção contra SSRF)",
        "Preenchimento manual",
      ]}
    />
  );
}

export function MatchPage() {
  return (
    <ModulePlaceholder
      title="Compatibilidade"
      description="Score estimado, palavras-chave encontradas e as que faltam."
      phase={4}
      features={[
        "Score determinístico de 0 a 100 com pesos transparentes",
        "Estados: atendido, parcial, não identificado, não atendido, não avaliável",
        "Justificativas e recomendações",
      ]}
    />
  );
}

export function OptimizePage() {
  return (
    <ModulePlaceholder
      title="Currículo ATS"
      description="Gere, edite, compare e exporte a versão otimizada para a vaga."
      phase={5}
      features={[
        "Otimização sem inventar experiências (validação anti-fabricação)",
        "Templates Clássico, Profissional e Executivo",
        "Editor com pré-visualização em tempo real e comparação antes/depois",
        "Exportação real em PDF e DOCX",
      ]}
    />
  );
}

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
