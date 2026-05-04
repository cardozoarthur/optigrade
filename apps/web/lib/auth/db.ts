import { Pool } from "pg";

const connectionString =
  process.env.BETTER_AUTH_DATABASE_URL ??
  process.env.DATABASE_URL ??
  "postgresql://optigrade:optigrade@localhost:55432/optigrade";

const globalForPool = globalThis as unknown as {
  optigradeAuthPool?: Pool;
};

export const authDb =
  globalForPool.optigradeAuthPool ??
  new Pool({
    connectionString
  });

if (process.env.NODE_ENV !== "production") {
  globalForPool.optigradeAuthPool = authDb;
}
