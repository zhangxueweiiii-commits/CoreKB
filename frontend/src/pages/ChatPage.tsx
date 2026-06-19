import { FormEvent, useEffect, useState } from "react";
import { api, type KnowledgeBase } from "../api/client";

interface Citation {
  filename: string;
  page_number?: number;
  section_title?: string;
  sheet_name?: string;
  row_start?: number;
  row_end?: number;
  quote: string;
}

export function ChatPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [error, setError] = useState("");
  const [streaming, setStreaming] = useState(true);
  const [running, setRunning] = useState(false);
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    api.kbs()
      .then((data) => {
        setKbs(data);
        if (data[0]) setSelectedKbIds([data[0].id]);
      })
      .catch((err) => setError(err.message));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setAnswer("");
    setCitations([]);
    setStatusText("");
    setRunning(true);
    try {
      if (streaming) {
        await api.streamChat({ message, knowledge_base_ids: selectedKbIds }, (event) => {
          if (event.event === "retrieval_started") setStatusText(event.data.message);
          if (event.event === "retrieval_completed") setStatusText(`已检索到 ${event.data.chunk_count} 个片段`);
          if (event.event === "token") setAnswer((current) => current + event.data.text);
          if (event.event === "citations") setCitations(event.data);
          if (event.event === "done") setStatusText("完成");
          if (event.event === "error") {
            setError(event.data.message);
            setStatusText("");
          }
        });
      } else {
        const data = await api.chat({ message, knowledge_base_ids: selectedKbIds });
        setAnswer(data.answer);
        setCitations(data.citations);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "问答失败");
    } finally {
      setRunning(false);
    }
  }

  function citationLabel(item: Citation) {
    if (item.sheet_name) {
      const rows = item.row_start && item.row_end ? ` / Rows ${item.row_start}-${item.row_end}` : "";
      return `${item.filename} / Sheet: ${item.sheet_name}${rows}`;
    }
    const page = item.page_number ? ` / p.${item.page_number}` : "";
    const section = item.section_title ? ` / ${item.section_title}` : "";
    return `${item.filename}${page}${section}`;
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>知识库问答</h2>
        <label className="toggle-row">
          <input type="checkbox" checked={streaming} onChange={(event) => setStreaming(event.target.checked)} />
          流式输出
        </label>
      </div>
      <div className="kb-picker">
        {kbs.map((kb) => (
          <label key={kb.id}>
            <input
              type="checkbox"
              checked={selectedKbIds.includes(kb.id)}
              onChange={(event) =>
                setSelectedKbIds((current) =>
                  event.target.checked ? [...current, kb.id] : current.filter((id) => id !== kb.id),
                )
              }
            />
            {kb.name}
          </label>
        ))}
      </div>
      <form className="chat-form" onSubmit={submit}>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="输入问题" />
        <button type="submit" disabled={running || !message || selectedKbIds.length === 0}>
          {running ? "生成中..." : "发送"}
        </button>
      </form>
      {statusText && <p className="muted">{statusText}</p>}
      {error && <p className="error">{error}</p>}
      {answer && (
        <div className="answer">
          <h3>回答</h3>
          <p>{answer}</p>
          {citations.length > 0 && <h3>引用</h3>}
          {citations.map((item, index) => (
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
