import { FormEvent, useCallback, useEffect, useState } from "react";

import * as domainsApi from "@/api/domains";
import { ApiClientError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import type { DnsRecord, DomainStats, SendingDomain } from "@/types/domains";

const statusColors: Record<string, string> = {
  pending: "text-amber-400 bg-amber-400/10",
  verified: "text-emerald-400 bg-emerald-400/10",
  failed: "text-red-400 bg-red-400/10",
};

function purposeLabel(purpose: string): string {
  const labels: Record<string, string> = {
    ownership: "Ownership",
    spf: "SPF",
    dkim: "DKIM",
    dmarc: "DMARC",
  };
  return labels[purpose] ?? purpose;
}

async function copyText(text: string, label: string, onCopied: (msg: string) => void) {
  try {
    await navigator.clipboard.writeText(text);
    onCopied(`${label} copied.`);
  } catch {
    onCopied(`Could not copy ${label}. Select and copy manually.`);
  }
}

export function DomainsPage() {
  const [stats, setStats] = useState<DomainStats | null>(null);
  const [domains, setDomains] = useState<SendingDomain[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [initialExpandDone, setInitialExpandDone] = useState(false);
  const [selectedDomainIds, setSelectedDomainIds] = useState<string[]>([]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [statsRes, domainsRes] = await Promise.all([
        domainsApi.fetchDomainStats(),
        domainsApi.fetchDomains({ search: search || undefined }),
      ]);
      setStats(statsRes.stats);
      setDomains(domainsRes.domains);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load domains");
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (initialExpandDone || domains.length === 0) return;
    const needsAttention = domains.find(
      (d) => d.status === "failed" || d.status === "pending",
    );
    if (needsAttention) {
      setExpandedId(needsAttention.id);
    }
    setInitialExpandDone(true);
  }, [domains, initialExpandDone]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await domainsApi.createDomain({ domain: newDomain });
      setShowForm(false);
      setNewDomain("");
      setNotice("Domain added. Configure the DNS records below, then verify.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to add domain");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this domain?")) return;
    try {
      await domainsApi.deleteDomain(id);
      setNotice("Domain deleted.");
      if (expandedId === id) setExpandedId(null);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Delete failed");
    }
  }

  async function handleDeleteSelected() {
    if (
      !selectedDomainIds.length ||
      !confirm(`Delete ${selectedDomainIds.length} selected domain(s)?`)
    ) return;
    try {
      await Promise.all(selectedDomainIds.map((id) => domainsApi.deleteDomain(id)));
      if (expandedId && selectedDomainIds.includes(expandedId)) setExpandedId(null);
      setSelectedDomainIds([]);
      setNotice("Selected domains deleted.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to delete selected domains");
      await loadData();
    }
  }

  async function handleSetDefault(id: string) {
    try {
      await domainsApi.setDefaultDomain(id);
      setNotice("Default sending domain updated.");
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not set default");
    }
  }

  async function handleVerify(id: string) {
    setVerifyingId(id);
    setError("");
    setNotice("");
    try {
      const result = await domainsApi.verifyDomain(id);
      setNotice(result.message);
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Verification failed");
    } finally {
      setVerifyingId(null);
    }
  }

  async function handleToggleActive(domain: SendingDomain) {
    try {
      await domainsApi.updateDomain(domain.id, { is_active: !domain.is_active });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Update failed");
    }
  }

  function renderDnsRecords(records: DnsRecord[]) {
    const pendingRequired = records.filter((r) => r.required && !r.verified);

    return (
      <div className="mt-3 space-y-3">
        {pendingRequired.length > 0 && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
            <p className="font-semibold">Action required</p>
            <p className="mt-1 text-amber-200/90">
              Add the pending records in your DNS panel (Namecheap, cPanel, Cloudflare, etc.),
              then wait 5–30 minutes and click Verify.
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1">
              {pendingRequired.map((record) => (
                <li key={record.purpose}>
                  {purposeLabel(record.purpose)} — Host:{" "}
                  <span className="font-mono">{record.host_label ?? record.host}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {records.map((record) => (
          <div
            key={`${record.purpose}-${record.host}`}
            className="rounded-lg border border-slate-700 bg-slate-900/60 p-3"
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-indigo-300">
                  {purposeLabel(record.purpose)} ({record.type})
                </span>
                {record.required && !record.verified && (
                  <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                    Required
                  </span>
                )}
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  record.verified
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "bg-slate-500/10 text-slate-400"
                }`}
              >
                {record.verified ? "Verified" : "Pending"}
              </span>
            </div>
            {record.note && (
              <p className="mb-2 text-xs text-slate-400">{record.note}</p>
            )}
            <div className="space-y-2 text-xs">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-slate-500">
                  Host (DNS panel):{" "}
                  <span className="font-mono text-slate-300">
                    {record.host_label ?? record.host}
                  </span>
                </p>
                <button
                  type="button"
                  onClick={() =>
                    copyText(
                      record.host_label ?? record.host,
                      "Host",
                      setNotice,
                    )
                  }
                  className="text-indigo-400 hover:underline"
                >
                  Copy host
                </button>
              </div>
              <p className="text-slate-600">
                FQDN: <span className="font-mono text-slate-500">{record.host}</span>
              </p>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="break-all text-slate-500">
                  Value: <span className="font-mono text-slate-300">{record.value}</span>
                </p>
                {record.value && (
                  <button
                    type="button"
                    onClick={() => copyText(record.value, "Value", setNotice)}
                    className="shrink-0 text-indigo-400 hover:underline"
                  >
                    Copy value
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {notice}
        </div>
      )}

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <Card>
            <p className="text-sm text-slate-400">Total Domains</p>
            <p className="mt-2 text-3xl font-bold text-white">{stats.total}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Verified</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">{stats.verified}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Pending</p>
            <p className="mt-2 text-3xl font-bold text-amber-400">{stats.pending}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Failed</p>
            <p className="mt-2 text-3xl font-bold text-red-400">{stats.failed}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-400">Default Set</p>
            <p className="mt-2 text-3xl font-bold text-indigo-400">
              {stats.default_configured ? "Yes" : "No"}
            </p>
          </Card>
        </div>
      )}

      <Card title="Sending Domains">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search domains..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
          <Button onClick={() => setShowForm((open) => !open)}>
            {showForm ? "Close" : "+ Add Domain"}
          </Button>
          {selectedDomainIds.length > 0 && (
            <Button variant="danger" onClick={() => void handleDeleteSelected()}>
              Delete Selected ({selectedDomainIds.length})
            </Button>
          )}
        </div>

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="mb-6 rounded-lg border border-slate-700 bg-slate-900/50 p-4"
          >
            <h3 className="mb-4 text-sm font-semibold text-white">Add Sending Domain</h3>
            <Input
              label="Domain"
              required
              value={newDomain}
              onChange={(e) => setNewDomain(e.target.value)}
              placeholder="example.com"
            />
            <div className="mt-4 flex gap-2">
              <Button type="submit">Add Domain</Button>
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-500" />
          </div>
        ) : domains.length === 0 ? (
          <p className="py-12 text-center text-sm text-slate-500">
            No domains added yet. Add your first sending domain to get DNS records.
          </p>
        ) : (
          <div className="space-y-4">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                aria-label="Select all domains"
                checked={domains.length > 0 && selectedDomainIds.length === domains.length}
                onChange={(event) =>
                  setSelectedDomainIds(
                    event.target.checked ? domains.map((domain) => domain.id) : [],
                  )
                }
              />
              Select All
            </label>
            {domains.map((domain) => (
              <div
                key={domain.id}
                className="rounded-lg border border-slate-800 bg-slate-900/40 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="checkbox"
                        aria-label={`Select ${domain.domain}`}
                        checked={selectedDomainIds.includes(domain.id)}
                        onChange={(event) =>
                          setSelectedDomainIds((current) =>
                            event.target.checked
                              ? [...current, domain.id]
                              : current.filter((id) => id !== domain.id),
                          )
                        }
                      />
                      <h3 className="text-base font-semibold text-white">{domain.domain}</h3>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[domain.status]}`}
                      >
                        {domain.status}
                      </span>
                      {domain.is_default && (
                        <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-400">
                          Default
                        </span>
                      )}
                      {!domain.is_active && (
                        <span className="rounded-full bg-slate-500/10 px-2 py-0.5 text-xs text-slate-400">
                          Inactive
                        </span>
                      )}
                    </div>
                    {domain.last_verification_message && (
                      <p className="mt-1 text-xs text-slate-500">
                        {domain.last_verification_message}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedId(expandedId === domain.id ? null : domain.id)
                      }
                      className="text-xs text-indigo-400 hover:underline"
                    >
                      {expandedId === domain.id ? "Hide DNS" : "Show DNS"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleVerify(domain.id)}
                      disabled={verifyingId === domain.id}
                      className="text-xs text-indigo-400 hover:underline disabled:opacity-50"
                    >
                      {verifyingId === domain.id ? "Verifying..." : "Verify"}
                    </button>
                    {domain.status === "verified" && !domain.is_default && domain.is_active && (
                      <button
                        type="button"
                        onClick={() => handleSetDefault(domain.id)}
                        className="text-xs text-slate-400 hover:underline"
                      >
                        Set default
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleToggleActive(domain)}
                      className="text-xs text-slate-400 hover:underline"
                    >
                      {domain.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(domain.id)}
                      className="text-xs text-red-400 hover:underline"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {expandedId === domain.id && renderDnsRecords(domain.dns_records)}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
