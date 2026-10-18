"use client";

// Fachada das telas v1 sobre os primitivos shadcn de `components/ui/` (Story 1.4 — AD-17).
// Tela nova importa direto de `@/components/ui/<primitivo>`; esta fachada some quando as telas v1
// saírem (Story 10.6). Só tokens do DESIGN.md (globals.css), nunca cor crua.
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { Badge as UiBadge } from "@/components/ui/badge";
import { Button as UiButton } from "@/components/ui/button";
import { Input as UiInput } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export { cn };

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <UiInput {...props} className={cn("h-10", className)} />;
}

// <select> nativo (as telas v1 usam onChange/option); contorno `input` como os demais controles.
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(
        "h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50",
        className,
      )}
    >
      {children}
    </select>
  );
}

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium text-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  return (
    <UiButton
      {...props}
      variant={variant === "primary" ? "default" : "ghost"}
      className={cn("h-10 px-4", className)}
    />
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-lg border border-border bg-card p-5 shadow-card", className)}>
      {children}
    </div>
  );
}

// Selo de status (preço/scan) das telas v1, mapeado para os tons do Selo de estado do DESIGN.md.
const TONES = {
  gain: "bg-positive-tint text-positive",
  warning: "bg-warning-tint text-warning",
  accent: "bg-secondary text-secondary-foreground",
  loss: "bg-negative-tint text-negative",
} as const;

export function Badge({ tone, children }: { tone: keyof typeof TONES; children: ReactNode }) {
  return (
    <UiBadge className={cn("rounded-xs border-transparent px-1.5 py-0.5 text-xs", TONES[tone])}>
      {children}
    </UiBadge>
  );
}
