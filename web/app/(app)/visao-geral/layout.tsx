import { Suspense } from "react";

import { AreaTabs } from "@/components/shell/AreaTabs";

export default function AreaLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-section-gap">
      <Suspense>
        <AreaTabs area="visao-geral" />
      </Suspense>
      {children}
    </div>
  );
}
