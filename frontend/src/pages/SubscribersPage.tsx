import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import * as subscribersApi from "@/api/subscribers";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { Subscriber, SubscriberList, SubscriberStats } from "@/types/subscribers";

export function SubscribersPage() {
  const [stats, setStats] = useState<SubscriberStats | null>(null);
  const [lists, setLists] = useState<SubscriberList[]>([]);
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [selectedListId, setSelectedListId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isEmailsLoading, setIsEmailsLoading] = useState(false);
  const [isVerifyingCsv, setIsVerifyingCsv] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showAddList, setShowAddList] = useState(false);
  const [showAddSubscriber, setShowAddSubscriber] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [selectedListIds, setSelectedListIds] = useState<string[]>([]);
  const [selectedSubscriberIds, setSelectedSubscriberIds] = useState<string[]>([]);
  const [newSubscriber, setNewSubscriber] = useState({
    email: "",
    first_name: "",
    last_name: "",
  });

  const selectedList = useMemo(
    () => lists.find((list) => list.id === selectedListId) ?? null,
    [lists, selectedListId],
  );

  const loadLists = useCallback(async () => {
    const [statsRes, listsRes] = await Promise.all([
      subscribersApi.fetchStats(),
      subscribersApi.fetchLists(),
    ]);
    setStats(statsRes.stats);
    setLists(listsRes.lists);
    return listsRes.lists;
  }, []);

  const loadEmails = useCallback(async (listId: string, searchValue: string) => {
    if (!listId) {
      setSubscribers([]);
      return;
    }
    setIsEmailsLoading(true);
    try {
      const subsRes = await subscribersApi.fetchSubscribers({
        list_id: listId,
        search: searchValue || undefined,
      });
      setSubscribers(subsRes.subscribers);
    } finally {
      setIsEmailsLoading(false);
    }
  }, []);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const latestLists = await loadLists();
      const activeListId =
        selectedListId && latestLists.some((list) => list.id === selectedListId)
          ? selectedListId
          : "";
      if (activeListId !== selectedListId) {
        setSelectedListId(activeListId);
      }
      if (activeListId) {
        await loadEmails(activeListId, search);
      } else {
        setSubscribers([]);
      }
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load emails");
    } finally {
      setIsLoading(false);
    }
  }, [loadEmails, loadLists, search, selectedListId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handleCreateList(e: FormEvent) {
    e.preventDefault();
    try {
      const result = await subscribersApi.createList({ name: newListName });
      setNewListName("");
      setShowAddList(false);
      setNotice(`List "${result.list.name}" created.`);
      setSelectedListId(result.list.id);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to create list");
    }
  }

  async function handleCreateSubscriber(e: FormEvent) {
    e.preventDefault();
    if (!selectedListId) {
      setError("Select a list first, then add an email.");
      return;
    }
    try {
      await subscribersApi.createSubscriber({
        ...newSubscriber,
        list_ids: [selectedListId],
      });
      setNewSubscriber({ email: "", first_name: "", last_name: "" });
      setShowAddSubscriber(false);
      setNotice("Email added to the selected list.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to create email");
    }
  }

  async function handleImport(file: File) {
    try {
      // Do not pass selectedListId — each CSV creates/uses a list from its file name.
      const result = await subscribersApi.importSubscribers(file);
      const imported = result.import;
      setNotice(
        `Imported ${imported.created} new, updated ${imported.updated}` +
          (imported.source_filename ? ` from ${imported.source_filename}` : "") +
          (imported.list_name ? ` into list "${imported.list_name}"` : "") +
          ".",
      );
      const latest = await loadLists();
      setLists(latest);
      const stem = file.name.replace(/\.[^.]+$/, "").trim();
      const matched =
        (imported.list_id && latest.find((list) => list.id === imported.list_id)) ||
        latest.find((list) => list.source_filename === file.name) ||
        latest.find((list) => list.name === stem);
      if (matched) {
        setSelectedListId(matched.id);
        await loadEmails(matched.id, search);
      }
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Import failed");
    }
  }

  async function handleFilterCsv(file: File) {
    setIsVerifyingCsv(true);
    setError("");
    try {
      const result = await subscribersApi.filterCsvWithReacher(file);
      const filtered = result.filter;
      const verified = filtered.verify;
      setNotice(
        `Filtered "${filtered.list_name}": kept ${verified.kept} of ${verified.total}, removed ${verified.removed}.`,
      );
      const latest = await loadLists();
      setLists(latest);
      setSelectedListId(filtered.list_id);
      await loadEmails(filtered.list_id, search);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "CSV filter failed");
    } finally {
      setIsVerifyingCsv(false);
    }
  }

  async function handleVerifyList() {
    const listIdToVerify =
      selectedListId || selectedListIds[0] || lists[0]?.id || "";
    if (!listIdToVerify) {
      setError("No list to verify. Import a CSV first.");
      return;
    }
    setIsVerifyingCsv(true);
    setError("");
    try {
      setSelectedListId(listIdToVerify);
      const result = await subscribersApi.verifyList(listIdToVerify);
      const verified = result.verify;
      setNotice(
        `Verified "${verified.list_name}": kept ${verified.kept} of ${verified.total}, removed ${verified.removed}.`,
      );
      await loadLists();
      await loadEmails(listIdToVerify, search);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "List verification failed");
    } finally {
      setIsVerifyingCsv(false);
    }
  }

  async function handleDeleteSubscriber(id: string) {
    if (!confirm("Delete this email?")) return;
    try {
      await subscribersApi.deleteSubscriber(id);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
    }
  }

  async function handleDeleteList(id: string, name: string) {
    if (!confirm(`Delete list "${name}"?`)) return;
    try {
      await subscribersApi.deleteList(id);
      if (selectedListId === id) {
        setSelectedListId("");
        setSubscribers([]);
      }
      setNotice(`List "${name}" deleted.`);
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete list");
    }
  }

  async function handleDeleteAllLists() {
    if (!confirm("Delete all email lists?")) return;
    try {
      await Promise.all(lists.map((list) => subscribersApi.deleteList(list.id)));
      setSelectedListId("");
      setSubscribers([]);
      setNotice("All email lists deleted.");
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete all lists");
      await loadLists();
    }
  }

  async function handleDeleteSelectedLists() {
    if (!selectedListIds.length || !confirm(`Delete ${selectedListIds.length} selected list(s)?`)) return;
    try {
      await Promise.all(selectedListIds.map((id) => subscribersApi.deleteList(id)));
      if (selectedListIds.includes(selectedListId)) {
        setSelectedListId("");
        setSubscribers([]);
      }
      setSelectedListIds([]);
      setNotice("Selected email lists deleted.");
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete selected lists");
      await loadLists();
    }
  }

  async function handleDeleteSelectedSubscribers() {
    if (
      !selectedSubscriberIds.length ||
      !confirm(`Delete ${selectedSubscriberIds.length} selected email(s)?`)
    ) return;
    try {
      await subscribersApi.bulkDeleteSubscribers(selectedSubscriberIds);
      setSelectedSubscriberIds([]);
      setNotice("Selected emails deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete selected emails");
    }
  }

  async function handleSelectList(listId: string) {
    setSelectedListId(listId);
    setSelectedSubscriberIds([]);
    setError("");
    setIsEmailsLoading(true);
    try {
      await loadEmails(listId, search);
      const latest = await loadLists();
      setLists(latest);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load list emails");
    } finally {
      setIsEmailsLoading(false);
    }
  }

  const listTotals = selectedList
    ? {
        total: selectedList.total_emails ?? selectedList.subscriber_count ?? 0,
        sent: selectedList.sent_emails ?? 0,
        waiting: selectedList.waiting_emails ?? 0,
      }
    : null;

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

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-400">Total Emails</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{stats.total}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Lists</p>
            <p className="mt-2 text-3xl font-bold text-indigo-600">{stats.lists}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Selected list sent</p>
            <p className="mt-2 text-3xl font-bold text-emerald-600">
              {listTotals ? listTotals.sent : "—"}
            </p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Selected list waiting</p>
            <p className="mt-2 text-3xl font-bold text-amber-700">
              {listTotals ? listTotals.waiting : "—"}
            </p>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Email Lists"
          description="Each CSV import appears here with list name and file name"
        >
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <label className="cursor-pointer">
              <span className="inline-flex select-none caret-transparent items-center justify-center rounded-lg border border-slate-300 bg-slate-100 px-4 py-2.5 text-sm font-medium text-slate-900 hover:bg-slate-700">
                Import CSV
              </span>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleImport(file);
                  e.target.value = "";
                }}
              />
            </label>
            <label className={`cursor-pointer ${isVerifyingCsv ? "pointer-events-none opacity-60" : ""}`}>
              <span className="inline-flex select-none caret-transparent items-center justify-center rounded-lg border border-indigo-700/60 bg-indigo-950/40 px-4 py-2.5 text-sm font-medium text-indigo-900 hover:bg-indigo-900/40">
                {isVerifyingCsv ? "Filtering CSV…" : "Filter CSV"}
              </span>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                disabled={isVerifyingCsv}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleFilterCsv(file);
                  e.target.value = "";
                }}
              />
            </label>
            <Button
              variant="secondary"
              disabled={isVerifyingCsv || lists.length === 0}
              onClick={() => void handleVerifyList()}
            >
              {isVerifyingCsv ? "Verifying…" : "Verify List"}
            </Button>
            <Button variant="secondary" onClick={() => setShowAddList(true)}>
              + New List
            </Button>
            {lists.length > 0 && (
              <Button variant="danger" onClick={() => void handleDeleteAllLists()}>
                Delete All Lists
              </Button>
            )}
            {selectedListIds.length > 0 && (
              <Button variant="danger" onClick={() => void handleDeleteSelectedLists()}>
                Delete Selected ({selectedListIds.length})
              </Button>
            )}
          </div>

          {showAddList && (
            <form onSubmit={handleCreateList} className="mb-4 space-y-2 rounded-lg border border-slate-300 bg-slate-50 p-3">
              <Input
                label="List name"
                value={newListName}
                onChange={(e) => setNewListName(e.target.value)}
                required
              />
              <div className="flex gap-2">
                <Button type="submit">Save</Button>
                <Button type="button" variant="ghost" onClick={() => setShowAddList(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}

          <p className="mb-3 text-xs text-slate-500">
            CSV columns: <span className="font-mono">email</span>, optional{" "}
            <span className="font-mono">name</span>, <span className="font-mono">Company</span>,{" "}
            <span className="font-mono">Industrial Company</span>, <span className="font-mono">list</span>.
            <span className="font-mono"> Filter CSV</span> imports then filters with Reacher
            (keeps real emails, removes spam / no-inbox). Or import first, then{" "}
            <span className="font-mono">Verify List</span>. Lists show Verified / Not verified.
          </p>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
            </div>
          ) : lists.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500">
              No lists yet. Import a CSV or create a list.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="pb-3 pr-3">
                      <input
                        type="checkbox"
                        aria-label="Select all lists"
                        checked={lists.length > 0 && selectedListIds.length === lists.length}
                        onChange={(event) =>
                          setSelectedListIds(event.target.checked ? lists.map((list) => list.id) : [])
                        }
                      />
                    </th>
                    <th className="pb-3 pr-3 font-medium">List name</th>
                    <th className="pb-3 pr-3 font-medium">File name</th>
                    <th className="pb-3 pr-3 font-medium">Status</th>
                    <th className="pb-3 pr-3 font-medium">Total</th>
                    <th className="pb-3 pr-3 font-medium">Sent</th>
                    <th className="pb-3 pr-3 font-medium">Waiting</th>
                    <th className="pb-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {lists.map((list) => {
                    const isSelected = list.id === selectedListId;
                    return (
                      <tr
                        key={list.id}
                        onClick={() => void handleSelectList(list.id)}
                        className={`cursor-pointer border-b border-slate-200/60 transition ${
                          isSelected
                            ? "bg-indigo-50"
                            : "hover:bg-white"
                        }`}
                      >
                        <td className="py-3 pr-3">
                          <input
                            type="checkbox"
                            aria-label={`Select ${list.name}`}
                            checked={selectedListIds.includes(list.id)}
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) =>
                              setSelectedListIds((current) =>
                                event.target.checked
                                  ? [...current, list.id]
                                  : current.filter((id) => id !== list.id),
                              )
                            }
                          />
                        </td>
                        <td className="py-3 pr-3 font-medium text-slate-900">{list.name}</td>
                        <td className="py-3 pr-3 text-slate-400">
                          {list.source_filename || "—"}
                        </td>
                        <td className="py-3 pr-3">
                          {list.is_verified ? (
                            <span className="text-xs font-medium text-emerald-600">Verified</span>
                          ) : (
                            <span className="text-xs font-medium text-amber-700">Not verified</span>
                          )}
                        </td>
                        <td className="py-3 pr-3 text-slate-700">
                          {list.total_emails ?? list.subscriber_count}
                        </td>
                        <td className="py-3 pr-3 text-emerald-600">{list.sent_emails ?? 0}</td>
                        <td className="py-3 pr-3 text-amber-700">{list.waiting_emails ?? 0}</td>
                        <td className="py-3">
                          <button
                            type="button"
                            className="text-xs text-red-600 hover:text-red-700"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleDeleteList(list.id, list.name);
                            }}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card
          title={selectedList ? `Emails — ${selectedList.name}` : "Emails"}
          description={
            selectedList
              ? `File: ${selectedList.source_filename || "—"} · ${selectedList.is_verified ? "Verified" : "Not verified"} · Total ${listTotals?.total ?? 0} · Sent ${listTotals?.sent ?? 0} · Waiting ${listTotals?.waiting ?? 0}`
              : "Click a list on the left to see its emails"
          }
        >
          {!selectedListId ? (
            <p className="py-12 text-center text-sm text-slate-500">
              Select a list to view emails, sent status, and waiting emails.
            </p>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <input
                  type="search"
                  placeholder="Search emails in this list..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="min-w-[200px] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
                <Button onClick={() => setShowAddSubscriber(true)}>+ Add email</Button>
                {selectedSubscriberIds.length > 0 && (
                  <Button variant="danger" onClick={() => void handleDeleteSelectedSubscribers()}>
                    Delete Selected ({selectedSubscriberIds.length})
                  </Button>
                )}
              </div>

              {showAddSubscriber && (
                <form
                  onSubmit={handleCreateSubscriber}
                  className="mb-4 rounded-lg border border-slate-300 bg-slate-50 p-4"
                >
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Input
                      label="Email"
                      type="email"
                      required
                      value={newSubscriber.email}
                      onChange={(e) =>
                        setNewSubscriber((s) => ({ ...s, email: e.target.value }))
                      }
                    />
                    <Input
                      label="First name"
                      value={newSubscriber.first_name}
                      onChange={(e) =>
                        setNewSubscriber((s) => ({ ...s, first_name: e.target.value }))
                      }
                    />
                    <Input
                      label="Last name"
                      value={newSubscriber.last_name}
                      onChange={(e) =>
                        setNewSubscriber((s) => ({ ...s, last_name: e.target.value }))
                      }
                    />
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button type="submit">Add Email</Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setShowAddSubscriber(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              )}

              <p className="mb-3 text-xs text-slate-500">
                When you send a campaign with this list, only <strong>Waiting</strong> emails
                are queued. Already sent emails are skipped.
              </p>

              {isEmailsLoading ? (
                <div className="flex justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
                </div>
              ) : subscribers.length === 0 ? (
                <p className="py-12 text-center text-sm text-slate-500">
                  No emails in this list yet.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-500">
                        <th className="pb-3 pr-3">
                          <input
                            type="checkbox"
                            aria-label="Select all emails"
                            checked={
                              subscribers.length > 0 &&
                              selectedSubscriberIds.length === subscribers.length
                            }
                            onChange={(event) =>
                              setSelectedSubscriberIds(
                                event.target.checked ? subscribers.map((sub) => sub.id) : [],
                              )
                            }
                          />
                        </th>
                        <th className="pb-3 pr-4 font-medium">Email</th>
                        <th className="pb-3 pr-4 font-medium">Name</th>
                        <th className="pb-3 pr-4 font-medium">Send status</th>
                        <th className="pb-3 font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {subscribers.map((sub) => (
                        <tr key={sub.id} className="border-b border-slate-200/60">
                          <td className="py-3 pr-3">
                            <input
                              type="checkbox"
                              aria-label={`Select ${sub.email}`}
                              checked={selectedSubscriberIds.includes(sub.id)}
                              onChange={(event) =>
                                setSelectedSubscriberIds((current) =>
                                  event.target.checked
                                    ? [...current, sub.id]
                                    : current.filter((id) => id !== sub.id),
                                )
                              }
                            />
                          </td>
                          <td className="py-3 pr-4 text-slate-800">{sub.email}</td>
                          <td className="py-3 pr-4 text-slate-400">
                            {sub.full_name || "—"}
                          </td>
                          <td className="py-3 pr-4">
                            {sub.send_status === "sent" ? (
                              <span className="text-emerald-600">Sent</span>
                            ) : (
                              <span className="text-amber-700">Waiting</span>
                            )}
                          </td>
                          <td className="py-3 text-right">
                            <button
                              type="button"
                              onClick={() => void handleDeleteSubscriber(sub.id)}
                              className="text-xs text-red-600 hover:text-red-700"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
