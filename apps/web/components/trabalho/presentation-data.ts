export type TrabalhoSlideSlug =
  | "apresentacao"
  | "contexto-historico"
  | "problema-air-new-zealand"
  | "solucao-air-new-zealand"
  | "conclusao-artigo"
  | "problema-optigrade"
  | "projeto-optigrade"
  | "professor"
  | "alunos"
  | "parametros"
  | "comparacao"
  | "resultado"
  | "conclusao";

export type TrabalhoSlide = {
  index: number;
  slug: TrabalhoSlideSlug;
  title: string;
  eyebrow: string;
};

export const trabalhoSlides: TrabalhoSlide[] = [
  { index: 1, slug: "apresentacao", title: "Apresentação", eyebrow: "Quem apresenta" },
  { index: 2, slug: "contexto-historico", title: "Contexto histórico", eyebrow: "Pesquisa Operacional" },
  { index: 3, slug: "problema-air-new-zealand", title: "Problema raiz", eyebrow: "Air New Zealand" },
  { index: 4, slug: "solucao-air-new-zealand", title: "Solução apresentada", eyebrow: "Modelagem e impacto" },
  { index: 5, slug: "conclusao-artigo", title: "Conclusão do texto", eyebrow: "Leitura crítica" },
  { index: 6, slug: "problema-optigrade", title: "Problema universitário", eyebrow: "Origem do projeto" },
  { index: 7, slug: "projeto-optigrade", title: "Projeto OptiGrade", eyebrow: "MVP piloto" },
  { index: 8, slug: "professor", title: "Aplicação do professor", eyebrow: "QR Code temporário" },
  { index: 9, slug: "alunos", title: "Aplicação dos alunos", eyebrow: "Demanda real" },
  { index: 10, slug: "parametros", title: "Parâmetros do piloto", eyebrow: "Recursos e máquina" },
  { index: 11, slug: "comparacao", title: "Comparação dos projetos", eyebrow: "Air NZ x OptiGrade" },
  { index: 12, slug: "resultado", title: "Resultado da otimização", eyebrow: "Calendário final" },
  { index: 13, slug: "conclusao", title: "Conclusão textual", eyebrow: "Síntese acadêmica" }
];

export const slideAliases = Object.fromEntries(
  trabalhoSlides.map((slide) => [`slide${slide.index}`, slide.slug])
) as Record<string, TrabalhoSlideSlug>;

export function resolveSlide(value: string) {
  const normalized = value.toLowerCase();
  return trabalhoSlides.find((slide) => slide.slug === normalized)?.slug ?? slideAliases[normalized] ?? null;
}

export function slideBySlug(slug: TrabalhoSlideSlug) {
  return trabalhoSlides.find((slide) => slide.slug === slug) ?? trabalhoSlides[0];
}

export function nextSlide(slug: TrabalhoSlideSlug) {
  const slide = slideBySlug(slug);
  return trabalhoSlides[Math.min(slide.index, trabalhoSlides.length - 1)]?.slug ?? slug;
}

export function previousSlide(slug: TrabalhoSlideSlug) {
  const slide = slideBySlug(slug);
  return trabalhoSlides[Math.max(slide.index - 2, 0)]?.slug ?? slug;
}
