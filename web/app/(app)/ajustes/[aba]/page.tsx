"use client";

import { notFound, useParams } from "next/navigation";

import { TabPlaceholder } from "@/components/shell/TabPlaceholder";
import { getArea } from "@/lib/nav";

// Abas ainda não entregues; cada story cria a pasta estática da sua aba, que tem precedência.
export default function AbaPendente() {
  const { aba } = useParams<{ aba: string }>();
  if (!getArea("ajustes").tabs.some((t) => t.slug === aba)) notFound();
  return <TabPlaceholder area="ajustes" slug={aba} />;
}
