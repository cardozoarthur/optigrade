import { authDb } from "./db";

export async function bootstrapAdminExists() {
  const result = await authDb.query<{ exists: boolean }>(
    `
      select exists (
        select 1
        from auth_member
        where role = 'admin'
        limit 1
      ) as "exists"
    `
  );

  return result.rows[0]?.exists ?? false;
}
