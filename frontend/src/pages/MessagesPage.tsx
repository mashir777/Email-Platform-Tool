import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { ApiClientError } from "@/api/client";
import * as messagesApi from "@/api/messages";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { MessagePurpose, MessageVersion, MessageVersionKey } from "@/types/messages";

const VERSION_ORDER: MessageVersionKey[] = ["v1", "v2", "v3"];

export function MessagesPage() {
  const [purposes, setPurposes] = useState<MessagePurpose[]>([]);
  const [selectedPurposeId, setSelectedPurposeId] = useState("");
  const [selectedVersionKey, setSelectedVersionKey] = useState<MessageVersionKey>("v1");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showAddPurpose, setShowAddPurpose] = useState(false);
  const [newPurposeName, setNewPurposeName] = useState("");
  const [draftSubject, setDraftSubject] = useState("");
  const [draftHtml, setDraftHtml] = useState("");
  const [selectedPurposeIds, setSelectedPurposeIds] = useState<string[]>([]);

  const selectedPurpose = useMemo(
    () => purposes.find((purpose) => purpose.id === selectedPurposeId) ?? null,
    [purposes, selectedPurposeId],
  );

  const selectedVersion = useMemo(() => {
    if (!selectedPurpose) return null;
    return (
      selectedPurpose.versions.find((version) => version.version === selectedVersionKey) ?? null
    );
  }, [selectedPurpose, selectedVersionKey]);

  const loadPurposes = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const result = await messagesApi.fetchMessagePurposes();
      setPurposes(result.purposes);
      setSelectedPurposeId((current) =>
        current && result.purposes.some((purpose) => purpose.id === current)
          ? current
          : result.purposes[0]?.id ?? "",
      );
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load messages");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPurposes();
  }, [loadPurposes]);

  useEffect(() => {
    if (!selectedVersion) {
      setDraftSubject("");
      setDraftHtml("");
      return;
    }
    setDraftSubject(selectedVersion.subject);
    setDraftHtml(selectedVersion.html_content);
  }, [selectedVersion]);

  useEffect(() => {
    if (!selectedPurpose) return;
    if (!selectedPurpose.versions.some((version) => version.version === selectedVersionKey)) {
      setSelectedVersionKey("v1");
    }
  }, [selectedPurpose, selectedVersionKey]);

  async function handleCreatePurpose(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await messagesApi.createMessagePurpose({ name: newPurposeName.trim() });
      setNewPurposeName("");
      setShowAddPurpose(false);
      setNotice(`Purpose "${result.purpose.name}" created with V1/V2/V3.`);
      setSelectedPurposeId(result.purpose.id);
      setSelectedVersionKey("v1");
      await loadPurposes();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to create purpose");
    }
  }

  async function handleSaveVersion(event: FormEvent) {
    event.preventDefault();
    if (!selectedVersion) return;
    setIsSaving(true);
    setError("");
    try {
      await messagesApi.updateMessageVersion(selectedVersion.id, {
        subject: draftSubject,
        html_content: draftHtml,
      });
      setNotice(
        `${selectedPurpose?.name ?? "Message"} ${selectedVersionKey.toUpperCase()} saved.`,
      );
      await loadPurposes();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to save message");
    } finally {
      setIsSaving(false);
    }
  }

  function selectPurpose(purposeId: string) {
    setSelectedPurposeId(purposeId);
    setSelectedVersionKey("v1");
    setError("");
    setNotice("");
  }

  function selectVersion(version: MessageVersion) {
    setSelectedVersionKey(version.version);
    setDraftSubject(version.subject);
    setDraftHtml(version.html_content);
    setError("");
    setNotice("");
  }

  async function handleDeletePurpose(id: string, name: string) {
    if (!confirm(`Delete purpose "${name}" and all V1/V2/V3 messages?`)) return;
    try {
      await messagesApi.deleteMessagePurpose(id);
      if (selectedPurposeId === id) {
        setSelectedPurposeId("");
      }
      setSelectedPurposeIds((current) => current.filter((item) => item !== id));
      setNotice(`Purpose "${name}" deleted.`);
      await loadPurposes();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete purpose");
    }
  }

  async function handleDeleteAllPurposes() {
    if (!confirm("Delete all message purposes?")) return;
    try {
      await Promise.all(purposes.map((purpose) => messagesApi.deleteMessagePurpose(purpose.id)));
      setSelectedPurposeId("");
      setSelectedPurposeIds([]);
      setNotice("All message purposes deleted.");
      await loadPurposes();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete all purposes");
      await loadPurposes();
    }
  }

  async function handleDeleteSelectedPurposes() {
    if (
      !selectedPurposeIds.length ||
      !confirm(`Delete ${selectedPurposeIds.length} selected purpose(s)?`)
    ) return;
    try {
      await Promise.all(
        selectedPurposeIds.map((id) => messagesApi.deleteMessagePurpose(id)),
      );
      if (selectedPurposeIds.includes(selectedPurposeId)) {
        setSelectedPurposeId("");
      }
      setSelectedPurposeIds([]);
      setNotice("Selected message purposes deleted.");
      await loadPurposes();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete selected purposes");
      await loadPurposes();
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          {notice}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Card
          title="Message Purposes"
          description="Each purpose has V1, V2, and V3. Edit content anytime."
        >
          <div className="mb-4 flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setShowAddPurpose(true)}>
              + New Purpose
            </Button>
            {purposes.length > 0 && (
              <Button variant="danger" onClick={() => void handleDeleteAllPurposes()}>
                Delete All
              </Button>
            )}
            {selectedPurposeIds.length > 0 && (
              <Button variant="danger" onClick={() => void handleDeleteSelectedPurposes()}>
                Delete Selected ({selectedPurposeIds.length})
              </Button>
            )}
          </div>

          {showAddPurpose && (
            <form onSubmit={handleCreatePurpose} className="mb-4 space-y-2 rounded-lg border border-slate-300 bg-slate-50 p-3">
              <Input
                label="Purpose name"
                value={newPurposeName}
                onChange={(event) => setNewPurposeName(event.target.value)}
                placeholder="e.g. SaaS Work"
                required
              />
              <div className="flex gap-2">
                <Button type="submit">Save</Button>
                <Button type="button" variant="ghost" onClick={() => setShowAddPurpose(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {isLoading ? (
            <p className="py-8 text-center text-sm text-slate-500">Loading messages…</p>
          ) : purposes.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No purposes yet.</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-2 text-sm text-slate-400">
                <input
                  type="checkbox"
                  aria-label="Select all purposes"
                  checked={
                    purposes.length > 0 && selectedPurposeIds.length === purposes.length
                  }
                  onChange={(event) =>
                    setSelectedPurposeIds(
                      event.target.checked ? purposes.map((purpose) => purpose.id) : [],
                    )
                  }
                />
                <span>Select All</span>
              </div>
              <ul className="divide-y divide-slate-200">
                {purposes.map((purpose) => (
                  <li key={purpose.id} className="flex items-center">
                    <input
                      type="checkbox"
                      aria-label={`Select ${purpose.name}`}
                      checked={selectedPurposeIds.includes(purpose.id)}
                      onChange={(event) =>
                        setSelectedPurposeIds((current) =>
                          event.target.checked
                            ? [...current, purpose.id]
                            : current.filter((id) => id !== purpose.id),
                        )
                      }
                      className="ml-4"
                    />
                    <button
                      type="button"
                      onClick={() => selectPurpose(purpose.id)}
                      className={`min-w-0 flex-1 px-3 py-3 text-left text-sm transition ${
                        selectedPurposeId === purpose.id
                          ? "bg-indigo-50 text-indigo-800"
                          : "text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      <span className="block font-medium">{purpose.name}</span>
                      <span className="mt-0.5 block text-xs text-slate-500">V1 · V2 · V3</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeletePurpose(purpose.id, purpose.name)}
                      className="mr-4 text-xs text-red-600 hover:text-red-700"
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card
          title={selectedPurpose ? selectedPurpose.name : "Message Versions"}
          description={
            selectedPurpose
              ? "Attach one of these versions when creating a campaign (optional)."
              : "Select a purpose to edit its message versions."
          }
        >
          {!selectedPurpose ? (
            <p className="py-10 text-center text-sm text-slate-500">
              Select a purpose on the left.
            </p>
          ) : (
            <form onSubmit={handleSaveVersion} className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {VERSION_ORDER.map((key) => {
                  const version = selectedPurpose.versions.find((item) => item.version === key);
                  if (!version) return null;
                  const isActive = selectedVersionKey === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => selectVersion(version)}
                      className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive
                          ? "bg-indigo-600 text-white"
                          : "border border-slate-300 bg-slate-50 text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      {key.toUpperCase()}
                    </button>
                  );
                })}
              </div>

              <Input
                label={`${selectedVersionKey.toUpperCase()} Subject`}
                value={draftSubject}
                onChange={(event) => setDraftSubject(event.target.value)}
                placeholder="Optional subject for this version"
              />

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  {selectedVersionKey.toUpperCase()} HTML content
                </label>
                <textarea
                  rows={12}
                  value={draftHtml}
                  onChange={(event) => setDraftHtml(event.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
                  placeholder="Write the email message for this version. You can update it later."
                />
                <p className="mt-2 text-xs text-slate-500">
                  List CSV ke saare columns use ho sakte hain. Write {"{{first_name}}"},{" "}
                  {"{{Company}}"}, {"{{khush}}"}, or any header from your CSV inside{" "}
                  {"{{ }}"}. Signature ke liye {"{{sender_name}}"} — jo Sender select hoga
                  usi ka name aayega.
                </p>
              </div>

              <Button type="submit" isLoading={isSaving}>
                Save {selectedVersionKey.toUpperCase()}
              </Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
