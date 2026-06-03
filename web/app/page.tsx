import { redirect } from "next/navigation";

export default function Home() {
  // Entrada do app → dashboard. O proxy.ts redireciona p/ /login se não houver
  // sessão (cookie de refresh), então aqui só chega quem está autenticado.
  redirect("/dashboard");
}
