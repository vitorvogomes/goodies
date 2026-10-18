import { redirect } from "next/navigation";

import { HOME } from "@/lib/nav";

export default function Home() {
  // Entrada do app → Visão geral (Story 1.7). O proxy.ts redireciona p/ /login se não houver
  // sessão (cookie de refresh), então aqui só chega quem está autenticado.
  redirect(HOME);
}
