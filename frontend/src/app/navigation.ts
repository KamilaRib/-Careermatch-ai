import { Bot, Briefcase, FileText, Gauge, Home, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Início", icon: Home, description: "Visão geral" },
  { to: "/curriculo", label: "Currículo", icon: FileText, description: "Envie e revise seu currículo" },
  { to: "/vaga", label: "Vaga", icon: Briefcase, description: "Adicione a descrição da vaga" },
  { to: "/compatibilidade", label: "Compatibilidade", icon: Gauge, description: "Score e lacunas" },
  { to: "/curriculo-ats", label: "Currículo ATS", icon: Sparkles, description: "Otimize, edite e exporte" },
  { to: "/assistente", label: "Assistente", icon: Bot, description: "Career AI Assistant" },
  { to: "/privacidade", label: "Privacidade", icon: ShieldCheck, description: "Como tratamos seus dados" },
];
