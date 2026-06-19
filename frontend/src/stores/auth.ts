import { api, setToken, type User } from "../api/client";

export async function login(username: string, password: string): Promise<User> {
  const token = await api.login(username, password);
  setToken(token.access_token);
  return api.me();
}

export function logout(): void {
  setToken(null);
}
