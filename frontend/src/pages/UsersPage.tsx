import { FormEvent, useEffect, useState } from "react";
import { api, type User, type UserRole } from "../api/client";

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [error, setError] = useState("");

  async function load() {
    setUsers(await api.users());
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api.createUser({ username, password, role });
      setUsername("");
      setPassword("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  }

  return (
    <section className="panel">
      <h2>用户管理</h2>
      <form className="inline-form" onSubmit={create}>
        <input placeholder="用户名" value={username} onChange={(event) => setUsername(event.target.value)} />
        <input type="password" placeholder="初始密码" value={password} onChange={(event) => setPassword(event.target.value)} />
        <select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
          <option value="viewer">viewer</option>
          <option value="editor">editor</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit">创建用户</button>
      </form>
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>用户名</th>
            <th>邮箱</th>
            <th>角色</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.username}</td>
              <td>{user.email || ""}</td>
              <td>{user.role}</td>
              <td>{user.is_active ? "active" : "disabled"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
