import { FormEvent, useEffect, useState } from "react";
import {
  permissionsApi,
  type KbPermission,
  type KbPermissionRole,
} from "../api/permissions";
import type { UserSearchResult } from "../api/users";
import { UserSearchSelect } from "./UserSearchSelect";

interface Props {
  kbId: string;
}

export function KbPermissionManager({ kbId }: Props) {
  const [items, setItems] = useState<KbPermission[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null);
  const [role, setRole] = useState<KbPermissionRole>("viewer");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [canManage, setCanManage] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(await permissionsApi.list(kbId));
      setCanManage(true);
    } catch (err) {
      setCanManage(false);
      setError(err instanceof Error ? err.message : "当前账号没有管理该知识库权限的能力。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [kbId]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!selectedUser) return;
    setError("");
    try {
      await permissionsApi.create(kbId, { user_id: selectedUser.id, role });
      setSelectedUser(null);
      setRole("viewer");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加权限失败");
    }
  }

  async function update(permissionId: string, nextRole: KbPermissionRole) {
    setError("");
    try {
      await permissionsApi.update(kbId, permissionId, nextRole);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改权限失败");
    }
  }

  async function remove(permissionId: string) {
    setError("");
    try {
      await permissionsApi.remove(kbId, permissionId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除权限失败");
    }
  }

  if (!canManage) {
    return (
      <div className="subtle-block">
        <h3>权限管理</h3>
        <p className="muted">{error || "当前账号没有管理该知识库权限的能力。"}</p>
      </div>
    );
  }

  return (
    <div className="subtle-block">
      <h3>权限管理</h3>
      <form className="permission-form" onSubmit={create}>
        <UserSearchSelect
          kbId={kbId}
          excludedUserIds={items.map((item) => item.user_id)}
          onSelect={setSelectedUser}
        />
        <select value={role} onChange={(event) => setRole(event.target.value as KbPermissionRole)}>
          <option value="viewer">viewer</option>
          <option value="editor">editor</option>
          <option value="owner">owner</option>
        </select>
        <button type="submit" disabled={!selectedUser}>
          添加
        </button>
      </form>
      {loading && <p className="muted">加载权限列表...</p>}
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>用户</th>
            <th>邮箱</th>
            <th>知识库角色</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={4}>暂无授权用户</td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id}>
                <td>{item.username}</td>
                <td>{item.email || ""}</td>
                <td>
                  <select
                    value={item.role}
                    onChange={(event) => update(item.id, event.target.value as KbPermissionRole)}
                  >
                    <option value="viewer">viewer</option>
                    <option value="editor">editor</option>
                    <option value="owner">owner</option>
                  </select>
                </td>
                <td>
                  <button type="button" onClick={() => remove(item.id)}>
                    移除
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
