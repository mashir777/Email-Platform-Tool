import { FormEvent, useEffect, useState } from "react";

import * as authApi from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { getAuthErrorMessage, useAuth } from "@/context/AuthContext";

const timezoneOptions = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Asia/Dubai",
  "Asia/Karachi",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Australia/Sydney",
];

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);

  const [profileForm, setProfileForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    company_name: "",
    timezone: "UTC",
    default_reply_to: "",
  });

  const [passwordForm, setPasswordForm] = useState({
    old_password: "",
    password: "",
    password_confirm: "",
  });

  useEffect(() => {
    if (!user) return;
    setProfileForm({
      first_name: user.first_name ?? "",
      last_name: user.last_name ?? "",
      phone: user.phone ?? "",
      company_name: user.company_name ?? "",
      timezone: user.timezone ?? "UTC",
      default_reply_to: user.default_reply_to ?? "",
    });
  }, [user]);

  async function handleProfileSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setIsSavingProfile(true);
    try {
      await authApi.updateProfile(profileForm);
      await refreshUser();
      setNotice("Profile updated successfully.");
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    if (passwordForm.password !== passwordForm.password_confirm) {
      setError("New passwords do not match.");
      return;
    }
    setIsSavingPassword(true);
    try {
      await authApi.changePassword(passwordForm);
      setPasswordForm({ old_password: "", password: "", password_confirm: "" });
      setNotice("Password changed successfully.");
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setIsSavingPassword(false);
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
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      <Card title="Profile" description="Account information from authentication API">
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">Full name</dt>
            <dd className="mt-1 text-sm text-slate-800">
              {[user?.first_name, user?.last_name].filter(Boolean).join(" ") || "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Email</dt>
            <dd className="mt-1 text-sm text-slate-800">{user?.email}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Phone</dt>
            <dd className="mt-1 text-sm text-slate-800">{user?.phone || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Shared Reply-To</dt>
            <dd className="mt-1 text-sm text-slate-800">
              {user?.default_reply_to || "— (replies go to From address)"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Timezone</dt>
            <dd className="mt-1 text-sm text-slate-800">{user?.timezone}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Company</dt>
            <dd className="mt-1 text-sm text-slate-800">{user?.company_name || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Role</dt>
            <dd className="mt-1 text-sm capitalize text-slate-800">
              {user?.role.replace("_", " ")}
            </dd>
          </div>
        </dl>
      </Card>

      <Card title="Edit Profile" description="Update your account details">
        <form onSubmit={handleProfileSubmit} className="grid gap-3 sm:grid-cols-2">
          <Input
            label="First name"
            value={profileForm.first_name}
            onChange={(e) =>
              setProfileForm((f) => ({ ...f, first_name: e.target.value }))
            }
          />
          <Input
            label="Last name"
            value={profileForm.last_name}
            onChange={(e) =>
              setProfileForm((f) => ({ ...f, last_name: e.target.value }))
            }
          />
          <Input
            label="Phone"
            type="tel"
            placeholder="03001234567 or +923001234567"
            value={profileForm.phone}
            onChange={(e) => setProfileForm((f) => ({ ...f, phone: e.target.value }))}
          />
          <Input
            label="Company"
            value={profileForm.company_name}
            onChange={(e) =>
              setProfileForm((f) => ({ ...f, company_name: e.target.value }))
            }
          />
          <div className="sm:col-span-2">
            <Input
              label="Shared Reply-To inbox"
              type="email"
              placeholder="unsub@datrixworld.com"
              value={profileForm.default_reply_to}
              onChange={(e) =>
                setProfileForm((f) => ({ ...f, default_reply_to: e.target.value }))
              }
            />
            <p className="mt-1.5 text-xs text-slate-500">
              One mailbox for replies from all senders (20 or 200). Create this address
              on your hosting first. Leave blank to reply to each From address.
            </p>
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Timezone
            </label>
            <select
              value={profileForm.timezone}
              onChange={(e) =>
                setProfileForm((f) => ({ ...f, timezone: e.target.value }))
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
            >
              {timezoneOptions.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" isLoading={isSavingProfile}>
              Save Profile
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Change Password" description="Update your account password">
        <form onSubmit={handlePasswordSubmit} className="grid max-w-md gap-3">
          <Input
            label="Current password"
            type="password"
            required
            value={passwordForm.old_password}
            onChange={(e) =>
              setPasswordForm((f) => ({ ...f, old_password: e.target.value }))
            }
          />
          <Input
            label="New password"
            type="password"
            required
            minLength={10}
            value={passwordForm.password}
            onChange={(e) =>
              setPasswordForm((f) => ({ ...f, password: e.target.value }))
            }
          />
          <Input
            label="Confirm new password"
            type="password"
            required
            minLength={10}
            value={passwordForm.password_confirm}
            onChange={(e) =>
              setPasswordForm((f) => ({ ...f, password_confirm: e.target.value }))
            }
          />
          <Button type="submit" isLoading={isSavingPassword}>
            Change Password
          </Button>
        </form>
      </Card>
    </div>
  );
}
