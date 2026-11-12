import { Link } from "react-router-dom";
import { ArrowRight, Briefcase, FileText, Gauge, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const STEPS = [
  { n: 1, icon: FileText, title: "Envie seu currículo", text: "Faça upload de um documento ou preencha seus dados." },
  { n: 2, icon: Briefcase, title: "Adicione a vaga", text: "Cole a descrição da oportunidade." },
  { n: 3, icon: Gauge, title: "Descubra sua compatibilidade", text: "Receba uma análise inteligente e recomendações." },
  { n: 4, icon: Sparkles, title: "Otimize seu currículo", text: "Gere uma versão personalizada e exporte." },
];

export default function HomePage() {
  return (
    <div className="flex flex-col gap-12">
      <section
        aria-labelledby="hero-title"
        className="from-primary-soft via-card to-accent-soft relative overflow-hidden rounded-2xl border bg-gradient-to-br px-6 py-12 md:px-12 md:py-16"
      >
        <div className="max-w-2xl">
          <h1 id="hero-title" className="text-3xl font-bold tracking-tight text-balance md:text-5xl">
            Seu próximo passo profissional começa aqui.
          </h1>
          <p className="text-muted-foreground mt-4 text-lg text-pretty">
            Descubra o quanto seu currículo combina com uma vaga e crie versões personalizadas com inteligência
            artificial.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button size="lg" asChild>
              <Link to="/curriculo">
                <FileText /> Analisar currículo
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/vaga">
                <Briefcase /> Comparar com vaga
              </Link>
            </Button>
            <Button size="lg" variant="accent" asChild>
              <Link to="/curriculo-ats">
                <Sparkles /> Criar currículo ATS
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-title">
        <h2 id="how-title" className="mb-6 text-xl font-semibold">
          Como funciona
        </h2>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ n, icon: Icon, title, text }) => (
            <li key={n}>
              <Card className="h-full">
                <CardHeader>
                  <div className="bg-secondary text-primary-strong mb-2 flex size-10 items-center justify-center rounded-lg">
                    <Icon className="size-5" aria-hidden />
                  </div>
                  <CardTitle>
                    {n}. {title}
                  </CardTitle>
                  <CardDescription>{text}</CardDescription>
                </CardHeader>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <Card className="bg-accent-soft border-amber-200">
          <CardContent className="flex flex-col gap-4 md:flex-row md:items-center">
            <ShieldCheck className="text-foreground size-8 shrink-0" aria-hidden />
            <div className="flex-1">
              <p className="font-semibold">Melhoramos como você se apresenta. Nunca inventamos experiências.</p>
              <p className="text-muted-foreground text-sm">
                O CareerMatch AI reorganiza e esclarece o que já está no seu currículo. Cargos, competências,
                certificações e resultados que você não informou nunca são adicionados.
              </p>
            </div>
            <Button variant="link" asChild>
              <Link to="/privacidade">
                Privacidade <ArrowRight />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
