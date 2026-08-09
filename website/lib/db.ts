import path from "node:path";
import fs from "node:fs";
import { DatabaseSync } from "node:sqlite";

// Unified QuoteDrive SQLite database. Used only in server components / route
// handlers (never imported by client components). node:sqlite is a Node built-in
// (>= 22.5), so no native module install and it works in the standalone build.

let dbPath: string | null = null;
function resolveDbPath(): string {
  if (dbPath) return dbPath;
  const env = process.env.QUOTEDRIVE_DB;
  if (env) { dbPath = env; return env; }
  const candidates = [
    path.join(process.cwd(), "data", "quotedrive.db"),
    path.join(process.cwd(), "..", "data", "quotedrive.db"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) { dbPath = c; return c; }
  }
  dbPath = path.join(process.cwd(), "data", "quotedrive.db");
  return dbPath;
}

let conn: DatabaseSync | null = null;
export function getConnection(): DatabaseSync {
  if (conn) return conn;
  conn = new DatabaseSync(resolveDbPath(), { readOnly: false });
  return conn;
}

export function all<T = any>(sql: string, ...params: any[]): T[] {
  return getConnection().prepare(sql).all(...params) as T[];
}
export function get<T = any>(sql: string, ...params: any[]): T | undefined {
  return getConnection().prepare(sql).get(...params) as T | undefined;
}
export function run(sql: string, ...params: any[]): { changes: number | bigint; lastInsertRowid: number | bigint } {
  return getConnection().prepare(sql).run(...params);
}
