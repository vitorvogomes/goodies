import { redirect } from "next/navigation";

export default function Home() {
  // Entrada do app. Sem sessão → login (a tela de login é a STORY-00-07;
  // a proteção de rota autenticada via proxy.ts também entra na 00-07).
  redirect("/login");
}
