import { PresentationProvider } from "@/components/trabalho/presentation-store";

export default function TrabalhoLayout({ children }: { children: React.ReactNode }) {
  return <PresentationProvider>{children}</PresentationProvider>;
}
