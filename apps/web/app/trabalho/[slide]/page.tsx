import { notFound, redirect } from "next/navigation";
import { requireAcademicSession } from "@/lib/auth/session";
import { PresentationDeck } from "@/components/trabalho/presentation-deck";
import { resolveSlide } from "@/components/trabalho/presentation-data";

export default async function TrabalhoSlidePage({
  params
}: {
  params: Promise<{ slide: string }>;
}) {
  await requireAcademicSession("presentation:manage");
  const { slide } = await params;
  const resolved = resolveSlide(slide);
  if (!resolved) notFound();
  if (resolved !== slide) redirect(`/trabalho/${resolved}`);
  return <PresentationDeck slug={resolved} />;
}
