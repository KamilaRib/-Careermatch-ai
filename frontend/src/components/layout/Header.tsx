import { useState } from "react";
import { Menu, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Logo, SidebarNav } from "@/components/layout/Sidebar";
import { useDeleteSession, useHealth } from "@/hooks/useSystem";

function ApiStatus() {
  const { data, isLoading, isError } = useHealth();
  if (isLoading) return <Badge variant="outline">Conectando…</Badge>;
  if (isError || !data) return <Badge variant="destructive">API indisponível</Badge>;
  if (!data.ai_configured)
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="accent" tabIndex={0}>IA não configurada</Badge>
        </TooltipTrigger>
        <TooltipContent>Defina a chave do provedor ({data.ai_provider}) no arquivo .env do backend.</TooltipContent>
      </Tooltip>
    );
  return <Badge variant="success">API online · {data.ai_provider}</Badge>;
}

export function Header() {
  const [open, setOpen] = useState(false);
  const del = useDeleteSession();

  const clearData = () =>
    del.mutate(undefined, {
      onSuccess: () => toast.success("Dados da sessão apagados."),
      onError: (e) => toast.error(e instanceof Error ? e.message : "Falha ao apagar dados."),
    });

  return (
    <header className="bg-background/80 sticky top-0 z-40 flex h-16 items-center gap-3 border-b px-4 backdrop-blur md:px-6">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Abrir menu">
            <Menu />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-4">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SheetDescription className="sr-only">Navegação principal</SheetDescription>
          <Logo />
          <SidebarNav onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="lg:hidden">
        <Logo />
      </div>
      <div className="ml-auto flex items-center gap-2">
        <ApiStatus />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={clearData} disabled={del.isPending} aria-label="Apagar dados da sessão">
              <Trash2 />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Apagar todos os dados desta sessão</TooltipContent>
        </Tooltip>
      </div>
    </header>
  );
}
