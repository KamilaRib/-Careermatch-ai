import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SECTIONS = [
  {
    title: "Sem cadastro",
    text: "Você usa a aplicação sem login. Uma sessão anônima e temporária é criada com um identificador aleatório armazenado em cookie HttpOnly.",
  },
  {
    title: "Retenção",
    text: "Currículos e vagas ficam apenas na memória do servidor durante a sessão. A sessão expira após um período de inatividade e é apagada automaticamente. Você também pode apagar tudo a qualquer momento pelo ícone de lixeira no topo.",
  },
  {
    title: "Provedores de IA",
    text: "Para estruturar e otimizar seu currículo, o texto é enviado ao provedor de IA configurado pelo operador (Google Gemini ou OpenAI). Esses provedores possuem suas próprias políticas de tratamento de dados. Evite incluir informações sensíveis desnecessárias, como documentos pessoais.",
  },
  {
    title: "Logs",
    text: "Registramos apenas métricas técnicas (tempo de resposta, erros). Conteúdo de currículos, prompts e chaves de API nunca são registrados.",
  },
  {
    title: "Veracidade",
    text: "A aplicação melhora a apresentação do que você já informou e nunca adiciona cargos, competências, certificações ou resultados que não constem no seu currículo.",
  },
];

export default function PrivacyPage() {
  return (
    <div>
      <PageHeader title="Privacidade" description="Como seus dados são tratados, em linha com os princípios da LGPD." />
      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.map((s) => (
          <Card key={s.title}>
            <CardHeader>
              <CardTitle>{s.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-muted-foreground text-sm leading-relaxed">{s.text}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
