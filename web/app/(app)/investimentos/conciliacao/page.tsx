"use client";

// Investimentos › Conciliação (Stories 7.7 e 7.9): os Cartões de corretora (caixa em corretora ×
// a caminho) e, abaixo, as posições do app × o consolidado B3 e × as carteiras.
import { BrokerCards } from "@/components/investimentos/BrokerCards";
import { ReconciliationTables } from "@/components/investimentos/ReconciliationTables";

export default function ConciliacaoPage() {
  return (
    <div className="space-y-section-gap">
      <div className="space-y-3">
        <h2 className="type-section-title">Corretoras</h2>
        <BrokerCards />
      </div>
      <ReconciliationTables />
    </div>
  );
}
