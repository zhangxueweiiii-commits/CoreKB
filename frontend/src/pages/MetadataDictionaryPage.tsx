import { useEffect, useState } from "react";
import { metadataDictionaryApi, type MetadataDictionaryEntry } from "../api/metadataDictionary";

const FIELD_OPTIONS = [
  "equipment_model",
  "fault_code",
  "material_code",
  "product_model",
  "sop_code",
  "process_name",
  "doc_type",
  "category",
];

export function MetadataDictionaryPage() {
  const [entries, setEntries] = useState<MetadataDictionaryEntry[]>([]);
  const [fieldName, setFieldName] = useState("");
  const [status, setStatus] = useState("active");
  const [keyword, setKeyword] = useState("");
  const [newField, setNewField] = useState("equipment_model");
  const [newCanonical, setNewCanonical] = useState("");
  const [newAliases, setNewAliases] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [editingDescription, setEditingDescription] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setEntries(await metadataDictionaryApi.list({ field_name: fieldName, status, keyword }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metadata dictionary");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createEntry() {
    setError("");
    try {
      await metadataDictionaryApi.create({
        field_name: newField,
        canonical_value: newCanonical,
        aliases: newAliases.split(",").map((item) => item.trim()).filter(Boolean),
        status: "active",
        description: newDescription,
      });
      setNewCanonical("");
      setNewAliases("");
      setNewDescription("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create metadata dictionary entry");
    }
  }

  async function addAlias(entry: MetadataDictionaryEntry) {
    const alias = window.prompt("Alias to add:");
    if (!alias) return;
    setError("");
    try {
      await metadataDictionaryApi.addAlias(entry.id, alias);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add alias");
    }
  }

  async function deleteAlias(entry: MetadataDictionaryEntry, alias: string) {
    setError("");
    try {
      await metadataDictionaryApi.deleteAlias(entry.id, alias);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete alias");
    }
  }

  async function saveDescription(entry: MetadataDictionaryEntry) {
    setError("");
    try {
      await metadataDictionaryApi.update(entry.id, {
        description: editingDescription[entry.id] ?? entry.description ?? "",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update description");
    }
  }

  async function setEntryStatus(entry: MetadataDictionaryEntry, nextStatus: "active" | "inactive") {
    setError("");
    try {
      await metadataDictionaryApi.update(entry.id, { status: nextStatus });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update entry status");
    }
  }

  return (
    <section className="panel wide">
      <div className="section-heading">
        <h2>Metadata dictionary</h2>
        <button type="button" onClick={load}>Refresh</button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="form-grid">
        <label>
          Field
          <select value={fieldName} onChange={(event) => setFieldName(event.target.value)}>
            <option value="">All</option>
            {FIELD_OPTIONS.map((field) => (
              <option key={field} value={field}>{field}</option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All</option>
            <option value="active">active</option>
            <option value="inactive">inactive</option>
          </select>
        </label>
        <label>
          Keyword
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} />
        </label>
      </div>
      <button type="button" onClick={load}>Apply filters</button>

      <div className="subtle-block">
        <h3>New canonical value</h3>
        <div className="form-grid">
          <label>
            Field
            <select value={newField} onChange={(event) => setNewField(event.target.value)}>
              {FIELD_OPTIONS.map((field) => (
                <option key={field} value={field}>{field}</option>
              ))}
            </select>
          </label>
          <label>
            Canonical value
            <input value={newCanonical} onChange={(event) => setNewCanonical(event.target.value)} />
          </label>
          <label>
            Aliases
            <input value={newAliases} placeholder="A-200, EQ-A200" onChange={(event) => setNewAliases(event.target.value)} />
          </label>
          <label>
            Description
            <input value={newDescription} onChange={(event) => setNewDescription(event.target.value)} />
          </label>
        </div>
        <button type="button" onClick={createEntry} disabled={!newCanonical}>Create entry</button>
      </div>

      {loading ? (
        <p className="muted">Loading...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Canonical</th>
              <th>Aliases</th>
              <th>Status</th>
              <th>Description</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr><td colSpan={7}>No dictionary entries.</td></tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.field_name}</td>
                  <td>{entry.canonical_value}</td>
                  <td>
                    {entry.aliases.length === 0 ? (
                      <span className="muted">No aliases</span>
                    ) : (
                      entry.aliases.map((alias) => (
                        <button key={alias} type="button" onClick={() => deleteAlias(entry, alias)}>
                          {alias} x
                        </button>
                      ))
                    )}
                  </td>
                  <td>{entry.status}</td>
                  <td>
                    <input
                      value={editingDescription[entry.id] ?? entry.description ?? ""}
                      onChange={(event) =>
                        setEditingDescription((current) => ({ ...current, [entry.id]: event.target.value }))
                      }
                    />
                  </td>
                  <td>{new Date(entry.updated_at).toLocaleString()}</td>
                  <td>
                    <button type="button" onClick={() => addAlias(entry)}>Add alias</button>
                    <button type="button" onClick={() => saveDescription(entry)}>Save description</button>
                    {entry.status === "active" ? (
                      <button type="button" onClick={() => setEntryStatus(entry, "inactive")}>Deactivate</button>
                    ) : (
                      <button type="button" onClick={() => setEntryStatus(entry, "active")}>Activate</button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </section>
  );
}
