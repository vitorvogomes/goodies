// Estado vazio de uma aba ainda não entregue (EXPERIENCE › State Patterns: título + frase).
import { type AreaKey, getArea } from "@/lib/nav";

export function TabPlaceholder({ area, slug }: { area: AreaKey; slug: string }) {
  const tab = getArea(area).tabs.find((t) => t.slug === slug);
  return (
    <div className="rounded-lg border border-border bg-card p-card-padding">
      <h2 className="type-section-title">{tab?.label}</h2>
      <p className="type-body text-muted-foreground">
        Esta aba chega na Story {tab?.story}. Até lá, use as telas da v1 acima.
      </p>
    </div>
  );
}
