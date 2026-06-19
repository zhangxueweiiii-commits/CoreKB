import { FormEvent, useEffect, useState } from "react";
import { api, type KnowledgeBase } from "../api/client";
import { KnowledgeBaseDetail } from "./KnowledgeBaseDetail";
import type { MetadataReviewFocus } from "../utils/metadataPrecheckNavigation";

interface Props {
  metadataReviewFocus?: MetadataReviewFocus | null;
  onMetadataReviewHandled?: () => void;
  onBackToMetadataPrecheck?: (search?: string | null) => void;
  onOpenJob?: (jobId: string) => void;
}

export function KnowledgeBasePage({
  metadataReviewFocus,
  onMetadataReviewHandled,
  onBackToMetadataPrecheck,
  onOpenJob,
}: Props) {
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [selected, setSelected] = useState<KnowledgeBase | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const data = await api.kbs();
    setItems(data);
    if (metadataReviewFocus?.documentId) {
      const document = await api.document(metadataReviewFocus.documentId);
      const targetKb = data.find((item) => item.id === document.knowledge_base_id);
      if (targetKb) {
        setSelected(targetKb);
        return;
      }
    }
    if (!selected && data[0]) setSelected(data[0]);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [metadataReviewFocus?.documentId]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const kb = await api.createKb({ name, description, visibility: "private" });
      setItems([kb, ...items]);
      setSelected(kb);
      setName("");
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建知识库失败");
    }
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <h2>知识库</h2>
        <form className="stack" onSubmit={create}>
          <input placeholder="名称" value={name} onChange={(event) => setName(event.target.value)} />
          <textarea
            placeholder="描述"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <button type="submit">创建知识库</button>
        </form>
        {error && <p className="error">{error}</p>}
        <div className="list">
          {items.length === 0 ? (
            <p className="muted">暂无知识库</p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                className={selected?.id === item.id ? "row active" : "row"}
                onClick={() => setSelected(item)}
              >
                <strong>{item.name}</strong>
                <span>{item.description || "无描述"}</span>
              </button>
            ))
          )}
        </div>
      </div>
      <KnowledgeBaseDetail
        knowledgeBase={selected}
        metadataReviewFocus={metadataReviewFocus}
        onMetadataReviewHandled={onMetadataReviewHandled}
        onBackToMetadataPrecheck={onBackToMetadataPrecheck}
        onOpenJob={onOpenJob}
      />
    </section>
  );
}
