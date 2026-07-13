import { FormEvent, useCallback, useEffect, useState } from "react";

import * as subscribersApi from "@/api/subscribers";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { Subscriber, SubscriberList, SubscriberStats } from "@/types/subscribers";

const statusColors: Record<string, string> = {
  subscribed: "text-emerald-400 bg-emerald-400/10",
  unsubscribed: "text-slate-400 bg-slate-400/10",
  bounced: "text-amber-400 bg-amber-400/10",
  complained: "text-red-400 bg-red-400/10",
};

export function SubscribersPage() {
  const [stats, setStats] = useState<SubscriberStats | null>(null);
  const [lists, setLists] = useState<SubscriberList[]>([]);
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [selectedListId, setSelectedListId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddList, setShowAddList] = useState(false);
  const [showAddSubscriber, setShowAddSubscriber] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [newSubscriber, setNewSubscriber] = useState({
    email: "",
    first_name: "",
    last_name: "",
  });

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [statsRes, listsRes, subsRes] = await Promise.all([
        subscribersApi.fetchStats(),
        subscribersApi.fetchLists(),
        subscribersApi.fetchSubscribers({
          list_id: selectedListId || undefined,
          search: search || undefined,
        }),
      ]);
      setStats(statsRes.stats);
      setLists(listsRes.lists);
      setSubscribers(subsRes.subscribers);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load subscribers");
    } finally {
      setIsLoading(false);
    }
  }, [selectedListId, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleCreateList(e: FormEvent) {
    e.preventDefault();
    try {
      await subscribersApi.createList({ name: newListName });
      setNewListName("");
      setShowAddList(false);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to create list");
    }
  }

  async function handleCreateSubscriber(e: FormEvent) {
    e.preventDefault();
    try {
      await subscribersApi.createSubscriber({
        ...newSubscriber,
        list_ids: selectedListId ? [selectedListId] : [],
      });
      setNewSubscriber({ email: "", first_name: "", last_name: "" });
      setShowAddSubscriber(false);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to create subscriber");
    }
  }

  async function handleImport(file: File) {
    try {
      await subscribersApi.importSubscribers(file, selectedListId || undefined);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Import failed");
    }
  }

  async function handleDeleteSubscriber(id: string) {
    if (!confirm("Delete this subscriber?")) return;
    try {
      await subscribersApi.deleteSubscriber(id);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-400">Total Subscribers</p>
            <p className="mt-2 text-3xl font-bold text-white">{stats.total}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Subscribed</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">{stats.subscribed}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Unsubscribed</p>
            <p className="mt-2 text-3xl font-bold text-slate-300">{stats.unsubscribed}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Lists</p>
            <p className="mt-2 text-3xl font-bold text-indigo-400">{stats.lists}</p>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-4">
        <Card title="Lists" className="lg:col-span-1">
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setSelectedListId("")}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                !selectedListId
                  ? "bg-indigo-600/15 text-indigo-300"
                  : "text-slate-400 hover:bg-slate-800"
              }`}
            >
              All Subscribers
            </button>
            {lists.map((list) => (
              <button
                key={list.id}
                type="button"
                onClick={() => setSelectedListId(list.id)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                  selectedListId === list.id
                    ? "bg-indigo-600/15 text-indigo-300"
                    : "text-slate-400 hover:bg-slate-800"
                }`}
              >
                <span className="truncate">{list.name}</span>
                <span className="ml-2 text-xs text-slate-500">{list.subscriber_count}</span>
              </button>
            ))}
          </div>
          {showAddList ? (
            <form onSubmit={handleCreateList} className="mt-4 space-y-2">
              <Input
                label="List name"
                value={newListName}
                onChange={(e) => setNewListName(e.target.value)}
                required
              />
              <div className="flex gap-2">
                <Button type="submit" className="flex-1">
                  Save
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowAddList(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <Button
              variant="secondary"
              className="mt-4 w-full"
              onClick={() => setShowAddList(true)}
            >
              + New List
            </Button>
          )}
        </Card>

        <Card title="Contacts" className="lg:col-span-3">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <input
              type="search"
              placeholder="Search by email or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
            />
            <Button onClick={() => setShowAddSubscriber(true)}>+ Add</Button>
            <label className="cursor-pointer">
              <span className="inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm font-medium text-slate-100 hover:bg-slate-700">
                Import CSV
              </span>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleImport(file);
                  e.target.value = "";
                }}
              />
            </label>
            <p className="w-full text-xs text-slate-500">
              CSV columns: <span className="font-mono">email</span>, optional{" "}
              <span className="font-mono">list</span> (e.g. AshirShahzad). Re-import to fix
              missing lists.
            </p>
          </div>

          {showAddSubscriber && (
            <form
              onSubmit={handleCreateSubscriber}
              className="mb-4 rounded-lg border border-slate-700 bg-slate-900/50 p-4"
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
                <Button type="submit">Add Subscriber</Button>
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

          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
            </div>
          ) : subscribers.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">
              No subscribers yet. Add one or import a CSV file.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500">
                    <th className="pb-3 pr-4 font-medium">Email</th>
                    <th className="pb-3 pr-4 font-medium">Name</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 pr-4 font-medium">Lists</th>
                    <th className="pb-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {subscribers.map((sub) => (
                    <tr key={sub.id} className="border-b border-slate-800/60">
                      <td className="py-3 pr-4 text-slate-200">{sub.email}</td>
                      <td className="py-3 pr-4 text-slate-400">
                        {sub.full_name || "—"}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[sub.status]}`}
                        >
                          {sub.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-slate-500">
                        {sub.lists.map((l) => l.name).join(", ") || "—"}
                      </td>
                      <td className="py-3 text-right">
                        <button
                          type="button"
                          onClick={() => handleDeleteSubscriber(sub.id)}
                          className="text-xs text-red-400 hover:text-red-300"
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
        </Card>
      </div>
    </div>
  );
}
