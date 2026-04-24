"use client";

import { useCallback, useState } from "react";
import { Users, Building2, X, Hash, GitBranch, Package, Mail, MessageCircle, ExternalLink } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalTenantsResponse, TemporalTenant } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface UserInfo {
  email: string;
  name: string;
  tenant: string;
  team: string;
  tenants: string[];
  permission: string;
}

function UserModal({ user, onClose }: { user: UserInfo; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl w-full max-w-sm mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-200">{user.name}</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-3">
          <div className="text-xs space-y-1.5">
            <div className="flex gap-2">
              <span className="text-zinc-500 w-16">Teams:</span>
              <span className="text-zinc-300">{user.tenants.join(", ")}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-zinc-500 w-16">Role:</span>
              <span className="text-zinc-300">{user.permission}</span>
            </div>
          </div>

          {/* Links */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center gap-2 text-xs">
              <Mail className="h-3 w-3 text-zinc-500 shrink-0" />
              <a href={`mailto:${user.email}`} className="text-zinc-300 hover:text-emerald-400">
                {user.email}
              </a>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <MessageCircle className="h-3 w-3 text-zinc-500 shrink-0" />
              <a
                href={`https://planetlabs.slack.com/team/${user.email.split("@")[0]}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-300 hover:text-emerald-400"
              >
                DM in Slack
              </a>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <ExternalLink className="h-3 w-3 text-zinc-500 shrink-0" />
              <a
                href={`https://planetlabs.bamboohr.com/employees/directory.php`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-300 hover:text-emerald-400"
              >
                BambooHR Directory
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TeamCard({ tenant }: { tenant: TemporalTenant }) {
  return (
    <div className="border border-zinc-800 rounded-lg p-3 bg-zinc-900/30 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="h-3.5 w-3.5 text-zinc-500" />
          <span className="text-xs font-medium text-zinc-200">{tenant.name}</span>
          <span className="text-[10px] text-zinc-600 font-mono">{tenant.uid}</span>
        </div>
        <div className="flex gap-1">
          {tenant.has_export && (
            <Badge className="bg-blue-600/10 text-blue-400 border-blue-600/30 text-[9px] px-1 py-0">Export</Badge>
          )}
          {tenant.has_nexus && (
            <Badge className="bg-purple-600/10 text-purple-400 border-purple-600/30 text-[9px] px-1 py-0">Nexus</Badge>
          )}
          {tenant.has_custom_sa && (
            <Badge className="bg-yellow-600/10 text-yellow-400 border-yellow-600/30 text-[9px] px-1 py-0">Custom SA</Badge>
          )}
        </div>
      </div>

      {/* Compact info grid */}
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[10px]">
        {/* Namespaces */}
        <span className="text-zinc-600">NS</span>
        <div className="flex flex-wrap gap-1">
          {tenant.namespaces.map((ns) => (
            <span key={ns} className="text-zinc-400 font-mono">{ns}</span>
          ))}
        </div>

        {/* Members */}
        <span className="text-zinc-600">Members</span>
        <div className="flex flex-wrap gap-x-2 gap-y-0.5">
          {tenant.users.length > 0 ? tenant.users.map((u) => (
            <span key={u.email} className="text-zinc-400">
              {u.name}
              <span className="text-zinc-600 ml-0.5">({u.permission})</span>
            </span>
          )) : (
            <span className="text-zinc-600">ACL group</span>
          )}
        </div>

        {/* Slack channels */}
        {tenant.slack_channels.length > 0 && (
          <>
            <span className="text-zinc-600">
              <Hash className="h-3 w-3 inline" />
            </span>
            <div className="flex flex-wrap gap-1">
              {tenant.slack_channels.map((ch) => (
                <a
                  key={ch}
                  href={`https://planet-labs.slack.com/channels/${ch}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-400 hover:text-emerald-400"
                >
                  #{ch}
                </a>
              ))}
            </div>
          </>
        )}

        {/* Repos */}
        {tenant.repos.length > 0 && (
          <>
            <span className="text-zinc-600">
              <GitBranch className="h-3 w-3 inline" />
            </span>
            <div className="flex flex-wrap gap-1">
              {tenant.repos.map((repo) => (
                <a
                  key={repo}
                  href={`https://hello.planet.com/code/${repo}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-400 hover:text-emerald-400 font-mono"
                >
                  {repo}
                </a>
              ))}
            </div>
          </>
        )}

        {/* Products */}
        {tenant.products.length > 0 && (
          <>
            <span className="text-zinc-600">
              <Package className="h-3 w-3 inline" />
            </span>
            <div className="flex flex-wrap gap-1">
              {tenant.products.map((p) => (
                <Badge key={p} className="bg-emerald-600/10 text-emerald-400 border-emerald-600/30 text-[9px] px-1 py-0">
                  {p}
                </Badge>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function TemporalUsers() {
  const fetcher = useCallback(() => api.temporalTenants(), []);
  const { data, loading, error } = usePoll<TemporalTenantsResponse>(fetcher, 3600_000);
  const [selectedUser, setSelectedUser] = useState<UserInfo | null>(null);
  const [filterTeam, setFilterTeam] = useState<string | null>(null);

  const filteredUsers = data?.users.filter((u) =>
    filterTeam ? u.tenants.includes(filterTeam) : true,
  ) ?? [];

  const filteredTenants = data?.tenants.filter((t) =>
    filterTeam ? t.uid === filterTeam : true,
  ) ?? [];

  return (
    <>
      <ScrollableCard
        title={`Users & Teams${data ? ` (${data.total_users} users, ${data.total_tenants} teams)` : ""}`}
        icon={<Users className="h-4 w-4" />}
       
      >
        {loading && <p className="text-xs text-zinc-500">Loading...</p>}
        {error && <p className="text-xs text-red-400">Failed to load tenant data</p>}
        {data && (
          <div className="space-y-3">
            {/* Team filter pills */}
            <div className="flex flex-wrap gap-1">
              <button
                onClick={() => setFilterTeam(null)}
                className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                  filterTeam === null
                    ? "border-emerald-600/40 bg-emerald-600/10 text-emerald-400"
                    : "border-zinc-700 text-zinc-400 hover:text-zinc-300"
                }`}
              >
                All
              </button>
              {data.tenants.map((t) => (
                <button
                  key={t.uid}
                  onClick={() => setFilterTeam(filterTeam === t.uid ? null : t.uid)}
                  className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                    filterTeam === t.uid
                      ? "border-emerald-600/40 bg-emerald-600/10 text-emerald-400"
                      : "border-zinc-700 text-zinc-400 hover:text-zinc-300 hover:border-zinc-600"
                  }`}
                >
                  {t.uid}
                  <span className="text-zinc-600 ml-1">{t.user_count}</span>
                </button>
              ))}
            </div>

            {/* Teams laid out as structured cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
              {filteredTenants.map((t) => (
                <TeamCard key={t.uid} tenant={t} />
              ))}
            </div>

            {/* Users list - click for modal */}
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wide mb-1">
                {filterTeam ? `${filterTeam} users` : "All users"} ({filteredUsers.length})
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-0.5 max-h-60 overflow-y-auto">
                {filteredUsers.map((u) => (
                  <button
                    key={u.email}
                    onClick={() => setSelectedUser(u)}
                    className="flex items-center justify-between text-xs py-0.5 px-1 rounded hover:bg-zinc-800/50 transition-colors text-left w-full"
                  >
                    <span className="text-zinc-300 truncate">{u.name}</span>
                    <span className="text-zinc-600 text-[10px] shrink-0 ml-2">
                      {u.tenants.join(", ")}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </ScrollableCard>

      {/* User modal */}
      {selectedUser && (
        <UserModal user={selectedUser} onClose={() => setSelectedUser(null)} />
      )}
    </>
  );
}
