// P0: a thin fetch wrapper. P5 replaces this with an Axios instance that adds the
// auth header and a refresh-token interceptor.

export interface Health {
  status: string;
  db: string;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<Health> {
  return getJson<Health>('/health');
}
