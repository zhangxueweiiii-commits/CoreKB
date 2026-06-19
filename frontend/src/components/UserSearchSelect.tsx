import { useEffect, useMemo, useState } from "react";
import { usersApi, type UserSearchResult } from "../api/users";

interface Props {
  kbId: string;
  excludedUserIds: string[];
  onSelect: (user: UserSearchResult | null) => void;
}

export function UserSearchSelect({ kbId, excludedUserIds, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<UserSearchResult[]>([]);
  const [selected, setSelected] = useState<UserSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const excluded = useMemo(() => new Set(excludedUserIds), [excludedUserIds]);

  useEffect(() => {
    const handle = window.setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const results = await usersApi.search(query, kbId);
        setItems(results.filter((user) => !excluded.has(user.id)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "用户搜索失败");
        setItems([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => window.clearTimeout(handle);
  }, [query, kbId, excluded]);

  function select(user: UserSearchResult) {
    setSelected(user);
    setQuery(user.name);
    onSelect(user);
  }

  return (
    <div className="user-search">
      <input
        placeholder="搜索姓名、用户名或邮箱"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setSelected(null);
          onSelect(null);
        }}
      />
      {selected && (
        <p className="muted">
          已选择：{selected.name}
          {selected.email ? ` / ${selected.email}` : ""} / {selected.role}
        </p>
      )}
      {loading && <p className="muted">搜索中...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && !selected && (
        <div className="search-results">
          {items.length === 0 ? (
            <p className="muted">没有可添加的用户</p>
          ) : (
            items.map((user) => (
              <button key={user.id} type="button" className="row" onClick={() => select(user)}>
                <strong>{user.name}</strong>
                <span>
                  {user.email || "无邮箱"} / {user.role}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
