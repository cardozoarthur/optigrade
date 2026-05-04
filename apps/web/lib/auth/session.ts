import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { authDb } from "./db";
import { auth } from "./server";
import {
  AcademicRole,
  academicRoleLabels,
  defaultPathForRole,
  normalizeAcademicRole,
  roleCan,
  type PermissionKey
} from "./permissions";

export type AcademicSession = {
  user: {
    id: string;
    name: string;
    email: string;
    profileType?: string | null;
    professorId?: string | null;
    studentId?: string | null;
  };
  session: {
    id: string;
    token: string;
    activeOrganizationId?: string | null;
  };
  organization: {
    id: string;
    name: string;
    slug: string;
  } | null;
  role: AcademicRole;
  roleLabel: string;
};

type MemberRow = {
  role: string;
  organizationId: string;
  organizationName: string;
  organizationSlug: string;
};

export async function getAcademicSession(): Promise<AcademicSession | null> {
  const session = await auth.api.getSession({
    headers: await headers()
  });

  if (!session) return null;

  const activeOrganizationId = "activeOrganizationId" in session.session
    ? (session.session.activeOrganizationId as string | null | undefined)
    : null;

  const member = await loadMember(session.user.id, activeOrganizationId);
  if (!member) return null;

  const role = normalizeAcademicRole(member?.role);

  return {
    user: {
      id: session.user.id,
      name: session.user.name,
      email: session.user.email,
      profileType: "profileType" in session.user ? (session.user.profileType as string | null | undefined) : null,
      professorId: "professorId" in session.user ? (session.user.professorId as string | null | undefined) : null,
      studentId: "studentId" in session.user ? (session.user.studentId as string | null | undefined) : null
    },
    session: {
      id: session.session.id,
      token: session.session.token,
      activeOrganizationId: member?.organizationId ?? activeOrganizationId ?? null
    },
    organization: member
      ? {
          id: member.organizationId,
          name: member.organizationName,
          slug: member.organizationSlug
        }
      : null,
    role,
    roleLabel: academicRoleLabels[role]
  };
}

export async function requireAcademicSession(permission?: PermissionKey) {
  const session = await getAcademicSession();
  if (!session) {
    redirect("/sign-in");
  }
  if (permission && !roleCan(session.role, permission)) {
    redirect(defaultPathForRole(session.role));
  }
  return session;
}

async function loadMember(userId: string, activeOrganizationId?: string | null): Promise<MemberRow | null> {
  const params = activeOrganizationId ? [userId, activeOrganizationId] : [userId];
  const activeFilter = activeOrganizationId ? `and m."organizationId" = $2` : "";
  const result = await authDb.query<MemberRow>(
    `
      select
        m.role as "role",
        m."organizationId" as "organizationId",
        o.name as "organizationName",
        o.slug as "organizationSlug"
      from auth_member m
      join auth_organization o on o.id = m."organizationId"
      where m."userId" = $1
      ${activeFilter}
      order by m."createdAt" asc
      limit 1
    `,
    params
  );

  if (result.rows[0]) return result.rows[0];
  if (!activeOrganizationId) return null;
  return loadMember(userId, null);
}
