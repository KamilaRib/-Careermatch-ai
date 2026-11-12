import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "@/app/navigation";
import { cn } from "@/lib/utils";

export function Logo() {
  return (
    <div className="flex items-center gap-2 px-2">
      <img src="/favicon.svg" alt="" className="size-8" aria-hidden />
      <span className="text-lg font-semibold tracking-tight">
        CareerMatch <span className="text-primary-strong">AI</span>
      </span>
    </div>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Navegação principal" className="flex flex-col gap-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="bg-sidebar border-sidebar-border sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-6 border-r p-4 lg:flex">
      <Logo />
      <SidebarNav />
      <p className="text-muted-foreground mt-auto px-2 text-xs leading-relaxed">
        Sem login. Seus dados ficam em uma sessão temporária e são apagados automaticamente.
      </p>
    </aside>
  );
}
