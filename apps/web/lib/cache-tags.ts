const CATALOG_RESOURCES = new Set([
  "campuses",
  "degree-programs",
  "courses",
  "course-restrictions",
  "professors",
  "rooms",
  "timeslots"
]);

const CACHEABLE_READS = new Set([...CATALOG_RESOURCES, "readiness"]);

const CATALOG_REVALIDATE_SECONDS = 300;
const READINESS_REVALIDATE_SECONDS = 30;
const OPTIMIZATION_RUN_REVALIDATE_SECONDS = 120;

export type BffReadCachePolicy = {
  revalidate: number;
  tags: string[];
};

export function getBffReadCachePolicy(path: string[], organizationId?: string | null): BffReadCachePolicy | null {
  const [resource] = path;
  if (resource === "optimization" && path[1] === "runs" && path.length === 3) {
    const runId = path[2];
    return {
      revalidate: OPTIMIZATION_RUN_REVALIDATE_SECONDS,
      tags: [
        scopedTag("optimization-runs", organizationId),
        scopedTag(`optimization-run:${runId}`, organizationId)
      ]
    };
  }

  if (!resource || path.length !== 1 || !CACHEABLE_READS.has(resource)) {
    return null;
  }

  const tags = tagsForResource(resource, organizationId);
  if (resource === "readiness") {
    return {
      revalidate: READINESS_REVALIDATE_SECONDS,
      tags
    };
  }

  return {
    revalidate: CATALOG_REVALIDATE_SECONDS,
    tags: [...tags, scopedTag("catalog", organizationId)]
  };
}

export function getBffMutationTags(path: string[], organizationId?: string | null): string[] {
  const [resource] = path;
  if (!resource) return [];

  const tags = new Set<string>([scopedTag("readiness", organizationId)]);

  if (resource === "imports") {
    tags.add(scopedTag("catalog", organizationId));
    for (const item of CATALOG_RESOURCES) {
      tags.add(scopedTag(item, organizationId));
    }
    return [...tags];
  }

  if (CATALOG_RESOURCES.has(resource)) {
    tags.add(scopedTag(resource, organizationId));
    tags.add(scopedTag("catalog", organizationId));
  }

  if (resource === "optimization") {
    tags.add(scopedTag("optimization-runs", organizationId));
    if (path[1] === "runs" && path[2]) {
      tags.add(scopedTag(`optimization-run:${path[2]}`, organizationId));
    }
  }

  if (resource === "students") {
    tags.add(scopedTag("students", organizationId));
  }

  return [...tags];
}

function tagsForResource(resource: string, organizationId?: string | null) {
  return [scopedTag(resource, organizationId), scopedTag("readiness", organizationId)];
}

function scopedTag(resource: string, organizationId?: string | null) {
  return `optigrade:${organizationId ?? "global"}:${resource}`;
}
