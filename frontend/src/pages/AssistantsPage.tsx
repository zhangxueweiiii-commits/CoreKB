import { FormEvent, useEffect, useState } from "react";
import { api, type AssistantChatResponse, type AssistantPreset } from "../api/client";

function citationLabel(item: AssistantChatResponse["citations"][number]) {
  if (item.sheet_name) {
    const rows = item.row_start && item.row_end ? ` / Rows ${item.row_start}-${item.row_end}` : "";
    return `${item.filename} / Sheet: ${item.sheet_name}${rows}`;
  }
  const page = item.page_number ? ` / p.${item.page_number}` : "";
  const section = item.section_title ? ` / ${item.section_title}` : "";
  return `${item.filename}${page}${section}`;
}

export function AssistantsPage() {
  const [presets, setPresets] = useState<AssistantPreset[]>([]);
  const [active, setActive] = useState<AssistantPreset | null>(null);
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<AssistantChatResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.assistantPresets()
      .then((items) => {
        setPresets(items);
        setActive(items[0] ?? null);
      })
      .catch((err) => setError(err.message));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!active) return;
    setRunning(true);
    setError("");
    setResponse(null);
    try {
      const data = await api.assistantChat(active.assistant_type, {
        query,
        auto_metadata_filter: active.default_auto_metadata_filter,
        use_rerank: active.default_use_rerank,
        rerank_top_n: active.default_rerank_top_n,
        top_k: active.default_top_k,
      });
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "助手问答失败");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>岗位助手</h2>
      </div>

      <div className="metric-grid">
        {presets.map((preset) => (
          <button
            key={preset.assistant_type}
            type="button"
            className={active?.assistant_type === preset.assistant_type ? "active" : ""}
            onClick={() => {
              setActive(preset);
              setResponse(null);
              setError("");
            }}
          >
            <strong>{preset.display_name}</strong>
            <br />
            <span className="muted">{preset.description}</span>
          </button>
        ))}
      </div>

      {active && (
        <div className="subtle-block">
          <h3>{active.display_name}</h3>
          <p className="muted">默认范围：{JSON.stringify(active.default_metadata_filter)}</p>
          <p className="muted">回答格式：{active.answer_format.join(" / ")}</p>
          <form className="chat-form" onSubmit={submit}>
            <textarea value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入岗位问题" />
            <button type="submit" disabled={running || !query.trim()}>
              {running ? "生成中..." : "发送"}
            </button>
          </form>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {response && (
        <div className="answer">
          <h3>回答</h3>
          <p>{response.answer}</p>
          <div className="detail-list">
            <dt>Metadata filter</dt>
            <dd>{JSON.stringify(response.used_metadata_filter)}</dd>
            <dt>Rerank</dt>
            <dd>{response.rerank_applied ? "已应用" : response.rerank_error || "未应用"}</dd>
          </div>
          {response.citations.length > 0 && <h3>引用</h3>}
          {response.citations.map((item, index) => (
            <blockquote key={`${item.filename}-${index}`}>
              <strong>{citationLabel(item)}</strong>
              <p>{item.quote}</p>
            </blockquote>
          ))}
        </div>
      )}
    </section>
  );
}
