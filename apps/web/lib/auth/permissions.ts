import { createAccessControl } from "better-auth/plugins/access";

export const academicStatements = {
  organization: ["read", "update", "delete"],
  member: ["create", "read", "update", "delete"],
  invitation: ["create", "read", "cancel"],
  catalog: ["read", "write"],
  faculty: ["read", "write", "self"],
  students: ["read", "write", "self"],
  optimization: ["read", "run", "adjust"],
  presentation: ["manage"],
  readiness: ["read"]
} as const;

export const academicAccessControl = createAccessControl(academicStatements);

export const academicRoles = {
  admin: academicAccessControl.newRole({
    organization: ["read", "update", "delete"],
    member: ["create", "read", "update", "delete"],
    invitation: ["create", "read", "cancel"],
    catalog: ["read", "write"],
    faculty: ["read", "write", "self"],
    students: ["read", "write", "self"],
    optimization: ["read", "run", "adjust"],
    presentation: ["manage"],
    readiness: ["read"]
  }),
  pro_reitoria: academicAccessControl.newRole({
    organization: ["read", "update"],
    member: ["create", "read", "update"],
    invitation: ["create", "read", "cancel"],
    catalog: ["read", "write"],
    faculty: ["read", "write", "self"],
    students: ["read", "write", "self"],
    optimization: ["read", "run", "adjust"],
    presentation: [],
    readiness: ["read"]
  }),
  chefe_departamento: academicAccessControl.newRole({
    organization: ["read", "update"],
    member: ["create", "read", "update"],
    invitation: ["create", "read", "cancel"],
    catalog: ["read", "write"],
    faculty: ["read", "write", "self"],
    students: ["read", "write"],
    optimization: ["read", "run", "adjust"],
    presentation: [],
    readiness: ["read"]
  }),
  coordenador: academicAccessControl.newRole({
    organization: ["read"],
    member: ["read"],
    invitation: ["create", "read"],
    catalog: ["read", "write"],
    faculty: ["read", "write", "self"],
    students: ["read", "write"],
    optimization: ["read", "run", "adjust"],
    presentation: [],
    readiness: ["read"]
  }),
  professor: academicAccessControl.newRole({
    organization: ["read"],
    member: ["read"],
    invitation: [],
    catalog: ["read"],
    faculty: ["read", "self"],
    students: [],
    optimization: ["read"],
    presentation: [],
    readiness: ["read"]
  }),
  student: academicAccessControl.newRole({
    organization: ["read"],
    member: [],
    invitation: [],
    catalog: ["read"],
    faculty: [],
    students: ["self"],
    optimization: [],
    presentation: [],
    readiness: []
  })
};

export const academicRoleLabels = {
  admin: "Administrador",
  pro_reitoria: "Pro-reitoria",
  chefe_departamento: "Chefia",
  coordenador: "Coordenacao",
  professor: "Professor",
  student: "Aluno"
} as const;

export type AcademicRole = keyof typeof academicRoles;

export type PermissionKey =
  | "organization:read"
  | "organization:manage"
  | "member:manage"
  | "invitation:manage"
  | "catalog:read"
  | "catalog:write"
  | "faculty:read"
  | "faculty:write"
  | "faculty:self"
  | "students:read"
  | "students:write"
  | "students:self"
  | "optimization:read"
  | "optimization:run"
  | "optimization:adjust"
  | "presentation:manage"
  | "readiness:read";

const rolePermissions: Record<AcademicRole, PermissionKey[]> = {
  admin: [
    "organization:read",
    "organization:manage",
    "member:manage",
    "invitation:manage",
    "catalog:read",
    "catalog:write",
    "faculty:read",
    "faculty:write",
    "faculty:self",
    "students:read",
    "students:write",
    "students:self",
    "optimization:read",
    "optimization:run",
    "optimization:adjust",
    "presentation:manage",
    "readiness:read"
  ],
  pro_reitoria: [
    "organization:read",
    "organization:manage",
    "member:manage",
    "invitation:manage",
    "catalog:read",
    "catalog:write",
    "faculty:read",
    "faculty:write",
    "faculty:self",
    "students:read",
    "students:write",
    "students:self",
    "optimization:read",
    "optimization:run",
    "optimization:adjust",
    "readiness:read"
  ],
  chefe_departamento: [
    "organization:read",
    "organization:manage",
    "member:manage",
    "invitation:manage",
    "catalog:read",
    "catalog:write",
    "faculty:read",
    "faculty:write",
    "faculty:self",
    "students:read",
    "students:write",
    "students:self",
    "optimization:read",
    "optimization:run",
    "optimization:adjust",
    "readiness:read"
  ],
  coordenador: [
    "organization:read",
    "invitation:manage",
    "catalog:read",
    "catalog:write",
    "faculty:read",
    "faculty:write",
    "faculty:self",
    "students:read",
    "students:write",
    "students:self",
    "optimization:read",
    "optimization:run",
    "optimization:adjust",
    "readiness:read"
  ],
  professor: ["organization:read", "catalog:read", "faculty:read", "faculty:self", "optimization:read", "readiness:read"],
  student: ["organization:read", "catalog:read", "students:self"]
};

export function normalizeAcademicRole(role: string | null | undefined): AcademicRole {
  const firstRole = role?.split(",").map((item) => item.trim()).find(Boolean);
  return firstRole && firstRole in academicRoles ? (firstRole as AcademicRole) : "student";
}

export function roleCan(role: AcademicRole, permission: PermissionKey) {
  return rolePermissions[role].includes(permission);
}

export function defaultPathForRole(role: AcademicRole) {
  if (role === "student") return "/app/aluno";
  if (role === "professor") return "/app/professor";
  return "/app/planejamento";
}
