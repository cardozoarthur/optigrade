import { notFound, redirect } from "next/navigation";
import { PresentationDeck } from "@/components/trabalho/presentation-deck";
import { resolveSlide } from "@/components/trabalho/presentation-data";

export default async function TrabalhoSlidePage({
  params
}: {
  params: Promise<{ slide: string }>;
}) {
  const { slide } = await params;
  const resolved = resolveSlide(slide);
  if (!resolved) notFound();
  if (resolved !== slide) redirect(`/trabalho/${resolved}`);
  return <PresentationDeck slug={resolved} />;
}
