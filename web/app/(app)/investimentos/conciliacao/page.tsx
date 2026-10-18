"use client";

// Investimentos › Conciliação (Story 7.7; a 7.9 junta a conciliação com o consolidado B3 e as
// carteiras): um Cartão de corretora por corretora — caixa em corretora × a caminho.
import { BrokerCards } from "@/components/investimentos/BrokerCards";

export default function ConciliacaoPage() {
  return (
    <div className="space-y-3">
      <h2 className="type-section-title">Corretoras</h2>
      <BrokerCards />
    </div>
  );
}
