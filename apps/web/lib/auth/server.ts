import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { organization } from "better-auth/plugins/organization";
import { Pool } from "pg";
import { academicAccessControl, academicRoles } from "./permissions";

const databaseUrl =
  process.env.BETTER_AUTH_DATABASE_URL ??
  process.env.DATABASE_URL ??
  "postgresql://optigrade:optigrade@localhost:55432/optigrade";

const baseUrl = process.env.BETTER_AUTH_URL ?? process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

const trustedOrigins = [
  baseUrl,
  process.env.NEXT_PUBLIC_APP_URL,
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "http://localhost:3301",
  "http://127.0.0.1:3301"
].filter(Boolean) as string[];

const authPool = new Pool({
  connectionString: databaseUrl
});

export const auth = betterAuth({
  appName: "OptiGrade",
  baseURL: baseUrl,
  secret: process.env.BETTER_AUTH_SECRET ?? "optigrade-dev-secret-change-before-pilot",
  trustedOrigins,
  database: authPool,
  user: {
    modelName: "auth_user",
    additionalFields: {
      profileType: {
        type: "string",
        required: false
      },
      professorId: {
        type: "string",
        required: false
      },
      studentId: {
        type: "string",
        required: false
      }
    }
  },
  session: {
    modelName: "auth_session"
  },
  account: {
    modelName: "auth_account"
  },
  verification: {
    modelName: "auth_verification"
  },
  emailAndPassword: {
    enabled: true,
    minPasswordLength: 8,
    autoSignIn: true
  },
  plugins: [
    organization({
      ac: academicAccessControl,
      roles: academicRoles,
      creatorRole: "admin",
      invitationExpiresIn: 60 * 60 * 24 * 7,
      allowUserToCreateOrganization: true,
      schema: {
        session: {
          fields: {
            activeOrganizationId: "activeOrganizationId"
          }
        },
        organization: {
          modelName: "auth_organization",
          additionalFields: {
            kind: {
              type: "string",
              required: false
            }
          }
        },
        member: {
          modelName: "auth_member"
        },
        invitation: {
          modelName: "auth_invitation"
        }
      },
      sendInvitationEmail: async (data) => {
        const url = `${baseUrl}/accept-invitation?id=${encodeURIComponent(data.id)}`;
        console.info("[OptiGrade] convite criado", {
          email: data.email,
          role: data.role,
          organization: data.organization.name,
          url
        });
      }
    }),
    nextCookies()
  ]
});

export type AuthSession = typeof auth.$Infer.Session;
