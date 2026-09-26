import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard, Users, Bell, Leaf, Mail, BarChart3,
  ChevronRight, RefreshCw, Search, ChevronLeft,
  ExternalLink, Shield, LogOut, Star, Layers,
  ArrowUpRight, X, Calendar, Activity, Inbox,
  CheckCircle2, Clock, XCircle, Send, TrendingUp,
  MapPin, User, Zap,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || '';
const ADMIN_EMAILS = ['chhelurathore773@gmail.com', 'karan270905@gmail.com'];

/* ── Config maps ──────────────────────────────────────────────────────────── */
const STATUS_CFG = {
  pending:   { label: 'Pending',   bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-400',   icon: Clock        },
  contacted: { label: 'Contacted', bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-400',    icon: Send         },
  approved:  { label: 'Approved',  bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', icon: CheckCircle2 },
  rejected:  { label: 'Rejected',  bg: 'bg-red-100',     text: 'text-red-600',     dot: 'bg-red-400',     icon: XCircle      },
};
const TIER_CFG = {
  free: { label: 'Free', bg: 'bg-gray-100',   text: 'text-gray-600'   },
  pro:  { label: 'Pro',  bg: 'bg-violet-100', text: 'text-violet-700' },
};

/* ── Shared helpers ───────────────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold ${cfg.bg} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
function TierBadge({ tier }) {
  const cfg = TIER_CFG[tier] || TIER_CFG.free;
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold ${cfg.bg} ${cfg.text}`}>
      {cfg.label}
    </span>
  );
}
function Avatar({ name, email, size = 'sm' }) {
  const initials = (name || email || '?').slice(0, 2).toUpperCase();
  const palette  = ['bg-emerald-500','bg-blue-500','bg-violet-500','bg-amber-500','bg-rose-500','bg-cyan-500'];
  const color    = palette[(name || email || '').charCodeAt(0) % palette.length];
  const dim      = size === 'lg' ? 'w-16 h-16 text-[22px]' : size === 'md' ? 'w-10 h-10 text-[14px]' : 'w-8 h-8 text-[11px]';
  return (
    <div className={`${dim} rounded-full ${color} flex items-center justify-center text-white font-black shrink-0`}>
      {initials}
    </div>
  );
}
function Loader() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 rounded-full border-[3px] border-emerald-100 border-t-emerald-500 animate-spin" />
    </div>
  );
}
const fmt     = dt => dt ? new Date(dt).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' }) : '—';
const fmtDate = dt => dt ? new Date(dt).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' }) : '—';

/* ── USER DRAWER ──────────────────────────────────────────────────────────── */
function UserDrawer({ userId, token, onClose, onTierChange }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    setData(null);
    fetch(`${API}/api/admin/users/${userId}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') setData(d); })
      .finally(() => setLoading(false));
  }, [userId, token]);

  const handleTier = async (tier) => {
    if (!data) return;
    setUpdating(true);
    await fetch(`${API}/api/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ tier }),
    });
    setUpdating(false);
    // Refresh drawer data
    const res = await fetch(`${API}/api/admin/users/${userId}`, { headers: { Authorization: `Bearer ${token}` } });
    const d   = await res.json();
    if (d.status === 'success') setData(d);
    onTierChange?.();
  };

  const updateRequestStatus = async (reqId, status) => {
    await fetch(`${API}/api/admin/access-requests/${reqId}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    // Refresh
    const res = await fetch(`${API}/api/admin/users/${userId}`, { headers: { Authorization: `Bearer ${token}` } });
    const d   = await res.json();
    if (d.status === 'success') setData(d);
  };

  const u  = data?.user;
  const reqs  = data?.access_requests || [];
  const scans = data?.scans || [];

  return (
    <AnimatePresence>
      {userId && (
        <>
          {/* Overlay */}
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]"
            onClick={onClose}
          />
          {/* Drawer */}
          <motion.aside
            key="drawer"
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="fixed top-0 right-0 h-full w-[500px] z-50 bg-white shadow-2xl flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-white">
              <p className="text-[13px] font-black text-[#0F172A] uppercase tracking-wider">User Profile</p>
              <button onClick={onClose} className="w-8 h-8 rounded-xl hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-700 transition-colors">
                <X size={16} />
              </button>
            </div>

            {loading ? <Loader /> : !u ? (
              <p className="text-center text-gray-400 p-8">User not found.</p>
            ) : (
              <div className="flex-1 overflow-y-auto">

                {/* ── Profile hero ── */}
                <div className="bg-gradient-to-br from-[#08292F] to-[#0d3d47] px-6 py-7">
                  <div className="flex items-start gap-4 mb-5">
                    <Avatar name={u.fullName} email={u.email} size="lg" />
                    <div className="flex-1 min-w-0 pt-1">
                      <h2 className="text-[20px] font-black text-white leading-tight truncate">{u.fullName || '—'}</h2>
                      <a href={`mailto:${u.email}`}
                        className="text-[13px] text-emerald-400 hover:text-emerald-300 transition-colors flex items-center gap-1 mt-0.5 truncate">
                        {u.email} <ExternalLink size={10} />
                      </a>
                      <div className="flex items-center gap-2 mt-2">
                        <TierBadge tier={u.tier} />
                        <span className="text-[11px] text-gray-400">·</span>
                        <span className="text-[11px] text-gray-300 flex items-center gap-1">
                          <Calendar size={10} /> Joined {fmtDate(u.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Quick stats */}
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { label: 'Requests', value: reqs.length },
                      { label: 'Scans',    value: scans.length },
                      { label: 'Status',   value: u.tier === 'pro' ? 'Pro' : 'Free' },
                    ].map(({ label, value }) => (
                      <div key={label} className="bg-white/10 rounded-xl px-3 py-2.5 text-center">
                        <p className="text-[18px] font-black text-white leading-none">{value}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5">{label}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── Account details ── */}
                <div className="px-6 py-5 border-b border-gray-100">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Account Details</p>
                  <div className="space-y-3">
                    {[
                      { icon: Activity, label: 'Primary Activity', value: u.primaryActivity || 'Not specified' },
                      { icon: User,     label: 'Account ID',       value: u._id },
                      { icon: Calendar, label: 'Member Since',      value: fmt(u.created_at) },
                    ].map(({ icon: Icon, label, value }) => (
                      <div key={label} className="flex items-start gap-3">
                        <div className="w-7 h-7 bg-gray-50 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                          <Icon size={12} className="text-gray-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
                          <p className="text-[13px] text-gray-700 font-medium truncate mt-0.5">{value}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── Free-tier usage ── */}
                <div className="px-6 py-5 border-b border-gray-100">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Free Usage Remaining</p>
                  {data?.usage?.unlimited ? (
                    <p className="text-[13px] font-bold text-violet-600">Unlimited (admin account)</p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {[['Land assessments', 'land_assess'], ['Land history', 'land_history'], ['AOI imports', 'aoi_import'], ['LULC reports', 'lulc_report']].map(([label, k]) => {
                        const a = data?.usage?.actions?.[k]; const rem = Math.max(0, a?.remaining ?? 3); const used = a?.used ?? 0;
                        return (
                          <div key={k} className="bg-gray-50 rounded-xl px-3 py-2.5">
                            <p className={`text-[16px] font-black leading-none ${rem <= 0 ? 'text-red-500' : 'text-[#0F172A]'}`}>{rem}/3</p>
                            <p className="text-[10px] text-gray-400 mt-1">{label} left · {used} used</p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* ── Tier action ── */}
                <div className="px-6 py-5 border-b border-gray-100">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Actions</p>
                  <div className="flex gap-2">
                    <a href={`mailto:${u.email}?subject=Your Sylithe Account`}
                      className="flex items-center gap-2 px-4 py-2.5 bg-[#08292F] hover:bg-[#062125] text-white font-bold rounded-xl text-[12px] transition-colors">
                      <Mail size={13} /> Send Email
                    </a>
                    {u.tier === 'free' ? (
                      <button onClick={() => handleTier('pro')} disabled={updating}
                        className="flex items-center gap-2 px-4 py-2.5 bg-violet-500 hover:bg-violet-600 text-white font-bold rounded-xl text-[12px] transition-colors disabled:opacity-50">
                        <Zap size={13} /> Upgrade to Pro
                      </button>
                    ) : (
                      <button onClick={() => handleTier('free')} disabled={updating}
                        className="flex items-center gap-2 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold rounded-xl text-[12px] transition-colors disabled:opacity-50">
                        Set to Free
                      </button>
                    )}
                  </div>
                </div>

                {/* ── Access Requests ── */}
                <div className="px-6 py-5 border-b border-gray-100">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">
                    Access Requests <span className="text-gray-300 normal-case font-normal">({reqs.length})</span>
                  </p>
                  {reqs.length === 0 ? (
                    <p className="text-[12px] text-gray-400 italic">No requests submitted yet.</p>
                  ) : (
                    <div className="space-y-2.5">
                      {reqs.map(r => (
                        <div key={r._id} className="bg-gray-50 rounded-xl p-4">
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <div>
                              <StatusBadge status={r.status} />
                              <p className="text-[11px] text-gray-400 mt-1">{fmt(r.requested_at)}</p>
                            </div>
                            <div className="flex gap-1.5 flex-wrap justify-end">
                              {r.status !== 'contacted' && (
                                <button onClick={() => updateRequestStatus(r._id, 'contacted')}
                                  className="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-[10px] font-bold rounded-lg transition-colors">
                                  Contacted
                                </button>
                              )}
                              {r.status !== 'approved' && (
                                <button onClick={() => updateRequestStatus(r._id, 'approved')}
                                  className="px-2 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-[10px] font-bold rounded-lg transition-colors">
                                  Approve
                                </button>
                              )}
                              {r.status !== 'rejected' && (
                                <button onClick={() => updateRequestStatus(r._id, 'rejected')}
                                  className="px-2 py-1 bg-red-50 hover:bg-red-100 text-red-600 text-[10px] font-bold rounded-lg transition-colors">
                                  Reject
                                </button>
                              )}
                            </div>
                          </div>
                          {r.admin_notes && (
                            <p className="text-[11px] text-gray-500 italic mt-1">Note: {r.admin_notes}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* ── Free Scans ── */}
                <div className="px-6 py-5">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">
                    Free Scans <span className="text-gray-300 normal-case font-normal">({scans.length})</span>
                  </p>
                  {scans.length === 0 ? (
                    <p className="text-[12px] text-gray-400 italic">No scans run yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {scans.map(s => (
                        <div key={s._id} className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-7 h-7 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0">
                              <MapPin size={12} className="text-emerald-600" />
                            </div>
                            <div>
                              <p className="text-[12px] font-semibold text-[#0F172A]">
                                {s.area_ha ? `${Number(s.area_ha).toFixed(1)} ha` : 'Area unknown'}
                              </p>
                              <p className="text-[10px] text-gray-400">{fmtDate(s.created_at)}</p>
                            </div>
                          </div>
                          <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${
                            s.status === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'
                          }`}>
                            {s.status || 'unknown'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

/* ── STAT CARD ────────────────────────────────────────────────────────────── */
function StatCard({ label, value, sub, icon: Icon, color, onClick }) {
  return (
    <div onClick={onClick}
      className={`bg-white rounded-2xl border border-gray-100 p-5 flex flex-col gap-3 shadow-sm hover:shadow-md transition-all ${onClick ? 'cursor-pointer hover:border-gray-200' : ''}`}>
      <div className="flex items-center justify-between">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={18} className="text-white" />
        </div>
        {onClick && <ArrowUpRight size={14} className="text-gray-300" />}
      </div>
      <div>
        <p className="text-[28px] font-black text-[#0F172A] leading-none">{value ?? '—'}</p>
        <p className="text-[12px] font-semibold text-gray-400 mt-1">{label}</p>
        {sub && <p className="text-[11px] text-gray-300 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

/* ── OVERVIEW ─────────────────────────────────────────────────────────────── */
function Overview({ stats, recentUsers, recentRequests, onNav }) {
  if (!stats) return <Loader />;
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-[20px] font-black text-[#0F172A] mb-1">Platform Overview</h2>
        <p className="text-[13px] text-gray-400">Live snapshot of all activity across the Sylithe platform.</p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Total Users"      value={stats.total_users}      icon={Users}      color="bg-[#08292F]"   onClick={() => onNav('users')} />
        <StatCard label="Free Tier"        value={stats.free_users}       icon={Leaf}       color="bg-emerald-500" sub={stats.total_users ? `${Math.round(stats.free_users/stats.total_users*100)}% of users` : ''} />
        <StatCard label="Pro Users"        value={stats.pro_users}        icon={Star}       color="bg-violet-500"  />
        <StatCard label="Access Requests"  value={stats.total_requests}   icon={Bell}       color="bg-amber-500"   onClick={() => onNav('requests')} />
        <StatCard label="Pending"          value={stats.pending_requests} icon={Inbox}      color="bg-rose-500"    onClick={() => onNav('requests')} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard label="Projects Cached"  value={stats.total_projects}   icon={Layers}     color="bg-blue-500"    />
        <StatCard label="Free Scans Run"   value={stats.total_scans}      icon={BarChart3}  color="bg-cyan-500"    onClick={() => onNav('scans')} />
        <StatCard label="Newsletter Subs"  value={stats.newsletter_subs}  icon={Mail}       color="bg-pink-500"    onClick={() => onNav('newsletter')} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent signups */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h3 className="text-[14px] font-black text-[#0F172A]">Recent Signups</h3>
            <button onClick={() => onNav('users')} className="text-[11px] text-emerald-600 font-bold hover:text-emerald-700 flex items-center gap-1">
              View all <ChevronRight size={12} />
            </button>
          </div>
          <div className="divide-y divide-gray-50">
            {recentUsers.length === 0
              ? <p className="text-[13px] text-gray-400 p-5">No users yet.</p>
              : recentUsers.map(u => (
                <div key={u._id} className="flex items-center gap-3 px-5 py-3.5">
                  <Avatar name={u.fullName} email={u.email} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-semibold text-[#0F172A] truncate">{u.fullName || u.email}</p>
                    <p className="text-[11px] text-gray-400 truncate">{u.email}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <TierBadge tier={u.tier} />
                    <p className="text-[10px] text-gray-400 mt-1">{fmtDate(u.created_at)}</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
        {/* Recent requests */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h3 className="text-[14px] font-black text-[#0F172A]">Recent Access Requests</h3>
            <button onClick={() => onNav('requests')} className="text-[11px] text-emerald-600 font-bold hover:text-emerald-700 flex items-center gap-1">
              View all <ChevronRight size={12} />
            </button>
          </div>
          <div className="divide-y divide-gray-50">
            {recentRequests.length === 0
              ? <p className="text-[13px] text-gray-400 p-5">No requests yet.</p>
              : recentRequests.map(r => (
                <div key={r._id} className="flex items-center gap-3 px-5 py-3.5">
                  <Avatar name={r.user_name} email={r.user_email} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-semibold text-[#0F172A] truncate">{r.user_name || r.user_email}</p>
                    <p className="text-[11px] text-gray-400 truncate">{r.user_email}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <StatusBadge status={r.status} />
                    <p className="text-[10px] text-gray-400 mt-1">{fmtDate(r.requested_at)}</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── ACCESS REQUESTS ──────────────────────────────────────────────────────── */
function AccessRequests({ token }) {
  const [rows, setRows]         = useState([]);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [filter, setFilter]     = useState('');
  const [loading, setLoading]   = useState(true);
  const [updating, setUpdating] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const q = new URLSearchParams({ page, limit: 50, ...(filter && { status: filter }) });
    const res  = await fetch(`${API}/api/admin/access-requests?${q}`, { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    setRows(data.requests || []);
    setTotal(data.total || 0);
    setLoading(false);
  }, [token, page, filter]);

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (id, status) => {
    setUpdating(id);
    await fetch(`${API}/api/admin/access-requests/${id}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    setUpdating(null);
    load();
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[20px] font-black text-[#0F172A] mb-1">Access Requests</h2>
          <p className="text-[13px] text-gray-400">{total} total requests</p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-[12px] text-gray-500 hover:bg-gray-50 transition-colors">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      <div className="flex gap-2 flex-wrap">
        {['', 'pending', 'contacted', 'approved', 'rejected'].map(s => (
          <button key={s} onClick={() => { setFilter(s); setPage(1); }}
            className={`px-4 py-2 rounded-xl text-[12px] font-bold transition-colors ${filter === s ? 'bg-[#08292F] text-white' : 'bg-white border border-gray-200 text-gray-500 hover:border-gray-300'}`}>
            {s === '' ? 'All' : STATUS_CFG[s]?.label}
          </button>
        ))}
      </div>
      {loading ? <Loader /> : (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
          {rows.length === 0 ? (
            <p className="text-[13px] text-gray-400 p-8 text-center">No requests found.</p>
          ) : (
            <table className="w-full text-left min-w-[700px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  {['User','Email','Phone','Plan','Tier','Activity','Requested','Status','Actions'].map(h => (
                    <th key={h} className="px-5 py-3.5 text-[10px] font-black text-gray-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {rows.map(r => (
                  <tr key={r._id} className="hover:bg-gray-50/60 transition-colors">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={r.user_name} email={r.user_email} />
                        <div className="min-w-0">
                          <span className="block text-[13px] font-semibold text-[#0F172A] whitespace-nowrap">{r.user_name || '—'}</span>
                          {r.user_company && <span className="block text-[11px] text-gray-400 truncate">{r.user_company}</span>}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <a href={`mailto:${r.user_email}`} className="text-[13px] text-emerald-600 hover:underline flex items-center gap-1 whitespace-nowrap">
                        {r.user_email} <ExternalLink size={10} />
                      </a>
                    </td>
                    <td className="px-5 py-4 text-[13px] text-gray-600 whitespace-nowrap">
                      {r.user_phone
                        ? <a href={`tel:${r.user_phone}`} className="hover:underline">{r.user_phone}</a>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-5 py-4">
                      {r.plan
                        ? <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded px-2 py-0.5 whitespace-nowrap">{r.plan}</span>
                        : <span className="text-[12px] text-gray-300">—</span>}
                    </td>
                    <td className="px-5 py-4"><TierBadge tier={r.user_tier} /></td>
                    <td className="px-5 py-4 text-[12px] text-gray-500 max-w-[120px] truncate">{r.activity || '—'}</td>
                    <td className="px-5 py-4 text-[12px] text-gray-400 whitespace-nowrap">{fmtDate(r.requested_at)}</td>
                    <td className="px-5 py-4"><StatusBadge status={r.status} /></td>
                    <td className="px-5 py-4">
                      <div className="flex gap-1.5 flex-wrap">
                        {r.status !== 'contacted' && (
                          <button onClick={() => updateStatus(r._id,'contacted')} disabled={updating===r._id}
                            className="px-2.5 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-[11px] font-bold rounded-lg disabled:opacity-50 whitespace-nowrap">Contacted</button>
                        )}
                        {r.status !== 'approved' && (
                          <button onClick={() => updateStatus(r._id,'approved')} disabled={updating===r._id}
                            className="px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-[11px] font-bold rounded-lg disabled:opacity-50">Approve</button>
                        )}
                        {r.status !== 'rejected' && (
                          <button onClick={() => updateStatus(r._id,'rejected')} disabled={updating===r._id}
                            className="px-2.5 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 text-[11px] font-bold rounded-lg disabled:opacity-50">Reject</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ── USERS ────────────────────────────────────────────────────────────────── */
function UsersSection({ token }) {
  const [rows, setRows]           = useState([]);
  const [total, setTotal]         = useState(0);
  const [page, setPage]           = useState(1);
  const [search, setSearch]       = useState('');
  const [query, setQuery]         = useState('');
  const [loading, setLoading]     = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const q = new URLSearchParams({ page, limit: 50, ...(query && { search: query }) });
    const res  = await fetch(`${API}/api/admin/users?${q}`, { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    setRows(data.users || []);
    setTotal(data.total || 0);
    setLoading(false);
  }, [token, page, query]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-[20px] font-black text-[#0F172A] mb-1">All Users</h2>
            <p className="text-[13px] text-gray-400">{total} registered users · click any row for full profile</p>
          </div>
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-[12px] text-gray-500 hover:bg-gray-50 transition-colors">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {/* Search */}
        <div className="relative max-w-sm">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { setQuery(search); setPage(1); } }}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 text-[13px] placeholder-gray-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 transition-all"
          />
        </div>

        {loading ? <Loader /> : (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
            {rows.length === 0 ? (
              <p className="text-[13px] text-gray-400 p-8 text-center">No users found.</p>
            ) : (
              <table className="w-full text-left min-w-[640px]">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    {['User','Email','Tier','Free usage left','Activity','Joined'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-[10px] font-black text-gray-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {rows.map(u => (
                    <tr key={u._id}
                      onClick={() => setSelectedId(u._id)}
                      className={`cursor-pointer transition-colors hover:bg-emerald-50/60 ${selectedId === u._id ? 'bg-emerald-50' : ''}`}>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2.5">
                          <Avatar name={u.fullName} email={u.email} />
                          <div>
                            <p className="text-[13px] font-semibold text-[#0F172A] whitespace-nowrap">{u.fullName || '—'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-[13px] text-emerald-600 whitespace-nowrap">{u.email}</td>
                      <td className="px-5 py-4"><TierBadge tier={u.tier} /></td>
                      <td className="px-5 py-4 text-[11px] whitespace-nowrap">
                        {u.usage?.unlimited
                          ? <span className="text-violet-600 font-bold">Unlimited</span>
                          : (() => { const a = u.usage?.actions || {}; const rem = (k) => a[k]?.remaining ?? 3;
                              const Item = ({ l, k }) => { const v = rem(k); return <span className={v <= 0 ? 'text-red-500 font-bold' : 'text-gray-600'}>{l} {Math.max(0, v)}/3</span>; };
                              return <div className="flex flex-wrap gap-x-2 gap-y-0.5 max-w-[180px]"><Item l="Assess" k="land_assess" /><Item l="History" k="land_history" /><Item l="Import" k="aoi_import" /><Item l="Report" k="lulc_report" /></div>;
                            })()}
                      </td>
                      <td className="px-5 py-4 text-[12px] text-gray-500 max-w-[160px] truncate">{u.primaryActivity || '—'}</td>
                      <td className="px-5 py-4 text-[12px] text-gray-400 whitespace-nowrap">{fmtDate(u.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {total > 50 && (
          <div className="flex items-center justify-between">
            <p className="text-[12px] text-gray-400">Showing {Math.min((page-1)*50+1, total)}–{Math.min(page*50, total)} of {total}</p>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(p-1,1))} disabled={page===1}
                className="flex items-center gap-1 px-3 py-2 rounded-xl border border-gray-200 text-[12px] disabled:opacity-40 hover:bg-gray-50">
                <ChevronLeft size={12} /> Prev
              </button>
              <button onClick={() => setPage(p => p+1)} disabled={page*50>=total}
                className="flex items-center gap-1 px-3 py-2 rounded-xl border border-gray-200 text-[12px] disabled:opacity-40 hover:bg-gray-50">
                Next <ChevronRight size={12} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Drawer */}
      <UserDrawer
        userId={selectedId}
        token={token}
        onClose={() => setSelectedId(null)}
        onTierChange={load}
      />
    </>
  );
}

/* ── FREE SCANS ───────────────────────────────────────────────────────────── */
function ScansSection({ token }) {
  const [rows, setRows]       = useState([]);
  const [total, setTotal]     = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res  = await fetch(`${API}/api/admin/scans?limit=50`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setRows(data.scans || []);
      setTotal(data.total || 0);
      setLoading(false);
    })();
  }, [token]);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-[20px] font-black text-[#0F172A] mb-1">Free Scans</h2>
        <p className="text-[13px] text-gray-400">{total} scans run on the platform</p>
      </div>
      {loading ? <Loader /> : (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
          {rows.length === 0 ? (
            <p className="text-[13px] text-gray-400 p-8 text-center">No scans yet.</p>
          ) : (
            <table className="w-full text-left min-w-[500px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  {['User','Area (ha)','Status','Date'].map(h => (
                    <th key={h} className="px-5 py-3.5 text-[10px] font-black text-gray-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {rows.map(s => (
                  <tr key={s._id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-4 text-[13px] text-gray-700">{s.email || s.user_email || '—'}</td>
                    <td className="px-5 py-4 text-[13px] font-semibold text-[#0F172A]">{s.area_ha ? Number(s.area_ha).toFixed(1) : '—'}</td>
                    <td className="px-5 py-4">
                      <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full ${s.status === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'}`}>
                        {s.status || '—'}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-[12px] text-gray-400 whitespace-nowrap">{fmt(s.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ── NEWSLETTER ───────────────────────────────────────────────────────────── */
function NewsletterSection({ token }) {
  const [rows, setRows]       = useState([]);
  const [total, setTotal]     = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res  = await fetch(`${API}/api/admin/newsletter?limit=50`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setRows(data.subscribers || []);
      setTotal(data.total || 0);
      setLoading(false);
    })();
  }, [token]);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-[20px] font-black text-[#0F172A] mb-1">Newsletter Subscribers</h2>
        <p className="text-[13px] text-gray-400">{total} subscribers</p>
      </div>
      {loading ? <Loader /> : (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {rows.length === 0 ? (
            <p className="text-[13px] text-gray-400 p-8 text-center">No subscribers yet.</p>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  {['Email','Subscribed'].map(h => (
                    <th key={h} className="px-5 py-3.5 text-[10px] font-black text-gray-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {rows.map(s => (
                  <tr key={s._id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-4">
                      <a href={`mailto:${s.email}`} className="text-[13px] text-emerald-600 hover:underline flex items-center gap-1">
                        {s.email} <ExternalLink size={10} />
                      </a>
                    </td>
                    <td className="px-5 py-4 text-[12px] text-gray-400">{fmt(s.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Boundary download helpers (GeoJSON + KML) ────────────────────────────── */
function downloadFile(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function geojsonToKml(gj, name = 'Boundary') {
  const rings = [];
  const walkPoly = (coords) => coords.map(ring =>
    `<LinearRing><coordinates>${ring.map(([x, y]) => `${x},${y},0`).join(' ')}</coordinates></LinearRing>`);
  const addGeom = (g) => {
    if (!g) return;
    if (g.type === 'Polygon') rings.push(`<Placemark><Polygon><outerBoundaryIs>${walkPoly(g.coordinates)[0]}</outerBoundaryIs></Polygon></Placemark>`);
    else if (g.type === 'MultiPolygon') g.coordinates.forEach(poly => rings.push(`<Placemark><Polygon><outerBoundaryIs>${walkPoly(poly)[0]}</outerBoundaryIs></Polygon></Placemark>`));
  };
  if (gj?.type === 'FeatureCollection') (gj.features || []).forEach(f => addGeom(f.geometry));
  else if (gj?.type === 'Feature') addGeom(gj.geometry);
  else addGeom(gj);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${name}</name>${rings.join('')}</Document></kml>`;
}

/* ── PROJECTS SECTION ─────────────────────────────────────────────────────── */
function ProjectsSection({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = search ? `?search=${encodeURIComponent(search)}` : '';
      const res = await fetch(`${API}/api/admin/projects${q}`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setRows(data.projects || []);
    } finally { setLoading(false); }
  }, [token, search]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[20px] font-black text-[#0F172A] mb-1">Submitted Projects</h2>
          <p className="text-[13px] text-gray-400">{rows.length} projects onboarded by developers · click a row for details & boundary</p>
        </div>
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name / email / country"
            className="pl-9 pr-3 py-2 rounded-xl border border-gray-200 text-[13px] w-64 outline-none focus:border-emerald-400" />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
        {loading ? (
          <p className="text-[13px] text-gray-400 p-8 text-center">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-[13px] text-gray-400 p-8 text-center">No projects submitted yet.</p>
        ) : (
          <table className="w-full text-left min-w-[820px]">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                {['Project', 'Developer', 'Type', 'Location', 'Area (ha)', 'Boundary', 'Created'].map(h => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-black text-gray-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map(p => (
                <tr key={p._id} onClick={() => setSelectedId(p._id)}
                  className={`cursor-pointer transition-colors hover:bg-emerald-50/60 ${selectedId === p._id ? 'bg-emerald-50' : ''}`}>
                  <td className="px-5 py-4 text-[13px] font-semibold text-[#0F172A] whitespace-nowrap">{p.name || '—'}</td>
                  <td className="px-5 py-4 text-[13px] text-emerald-600 whitespace-nowrap">{p.developer_email}</td>
                  <td className="px-5 py-4 text-[12px] text-gray-600">{p.type || '—'}</td>
                  <td className="px-5 py-4 text-[12px] text-gray-500 max-w-[180px] truncate">{[p.district, p.state, p.country].filter(Boolean).join(', ') || '—'}</td>
                  <td className="px-5 py-4 text-[12px] text-gray-700">{p.area_ha ? Number(p.area_ha).toLocaleString() : '—'}</td>
                  <td className="px-5 py-4">
                    {p.has_boundary
                      ? <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded px-2 py-0.5">{p.boundary_features || 1} polygon(s)</span>
                      : <span className="text-[12px] text-gray-300">none</span>}
                  </td>
                  <td className="px-5 py-4 text-[12px] text-gray-400 whitespace-nowrap">{fmtDate(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedId && <ProjectDrawer projectId={selectedId} token={token} onClose={() => setSelectedId(null)} />}
    </div>
  );
}

function ProjectDrawer({ projectId, token, onClose }) {
  const [p, setP] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true); setP(null);
    fetch(`${API}/api/admin/projects/${projectId}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(d => { if (d.status === 'success') setP(d.project); })
      .finally(() => setLoading(false));
  }, [projectId, token]);

  const safe = (p?.name || 'boundary').replace(/[^a-z0-9]+/gi, '-').toLowerCase();
  const fields = p ? [
    ['Developer', p.developer_email], ['Proponent', p.proponent], ['Type', p.type],
    ['Crediting Standard', p.crediting_standard], ['Methodology', p.methodology],
    ['Country', p.country], ['State', p.state], ['District', p.district],
    ['Area (ha)', p.area_ha], ['Project Length', p.project_length],
    ['Start Date', p.start_date], ['Crediting Start', p.credit_start], ['Crediting End', p.end_date],
    ['CCP Eligible', p.ccp_eligible], ['Land Tenure', p.land_tenure],
    ['Community Benefit', String(p.community_benefit)], ['Biodiversity', p.biodiversity_impact],
    ['Leakage Risk', p.leakage_risk], ['Contact', p.proponent_contact],
  ] : [];

  return (
    <div className="fixed inset-0 z-[80] flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-md h-full bg-white shadow-2xl overflow-y-auto">
        <div className="sticky top-0 bg-[#08292F] text-white px-6 py-5 flex items-start justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-wider text-emerald-300">Project</p>
            <h2 className="text-[18px] font-black leading-tight">{p?.name || '…'}</h2>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white"><X size={20} /></button>
        </div>

        {loading ? <p className="p-6 text-[13px] text-gray-400">Loading…</p> : p && (
          <div className="p-6 space-y-6">
            {/* boundary download */}
            <div>
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Uploaded Boundary</p>
              {p.geojson ? (
                <div className="flex gap-2">
                  <button onClick={() => downloadFile(`${safe}.geojson`, JSON.stringify(p.geojson, null, 2), 'application/geo+json')}
                    className="flex items-center gap-2 px-4 py-2.5 bg-[#08292F] hover:bg-[#062125] text-white font-bold rounded-xl text-[12px]">
                    <ArrowUpRight size={13} /> GeoJSON
                  </button>
                  <button onClick={() => downloadFile(`${safe}.kml`, geojsonToKml(p.geojson, p.name), 'application/vnd.google-earth.kml+xml')}
                    className="flex items-center gap-2 px-4 py-2.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold rounded-xl text-[12px] border border-emerald-100">
                    <ArrowUpRight size={13} /> KML
                  </button>
                </div>
              ) : <p className="text-[13px] text-gray-400">No boundary uploaded.</p>}
            </div>

            {/* fields */}
            <div>
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Project Details</p>
              <div className="space-y-2.5">
                {fields.map(([label, val]) => (
                  <div key={label} className="flex items-start justify-between gap-3 border-b border-gray-50 pb-2">
                    <span className="text-[12px] text-gray-400">{label}</span>
                    <span className="text-[13px] text-gray-800 font-medium text-right">{val || '—'}</span>
                  </div>
                ))}
              </div>
            </div>

            {p.description && (
              <div>
                <p className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-2">Description</p>
                <p className="text-[13px] text-gray-600 leading-relaxed">{p.description}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── NAV ──────────────────────────────────────────────────────────────────── */
const NAV = [
  { key: 'overview',   label: 'Overview',        icon: LayoutDashboard },
  { key: 'requests',   label: 'Access Requests',  icon: Bell            },
  { key: 'projects',   label: 'Projects',         icon: Layers          },
  { key: 'users',      label: 'Users',            icon: Users           },
  { key: 'scans',      label: 'Free Scans',       icon: BarChart3       },
  { key: 'newsletter', label: 'Newsletter',       icon: Mail            },
];

/* ── MAIN PANEL ───────────────────────────────────────────────────────────── */
export default function AdminPanel() {
  const { token, user, logout } = useAuth();
  const navigate = useNavigate();
  const [section, setSection]           = useState('overview');
  const [stats, setStats]               = useState(null);
  const [recentUsers, setRecentUsers]   = useState([]);
  const [recentReqs, setRecentReqs]     = useState([]);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    if (!token) { navigate('/login'); return; }
    if (user && !ADMIN_EMAILS.includes(user.email?.toLowerCase())) navigate('/');
  }, [token, user, navigate]);

  const loadStats = useCallback(async () => {
    if (!token) return;
    try {
      const res  = await fetch(`${API}/api/admin/stats`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (data.status === 'success') {
        setStats(data.stats);
        setRecentUsers(data.recent_users || []);
        setRecentReqs(data.recent_requests || []);
        setPendingCount(data.stats.pending_requests || 0);
      }
    } catch {}
  }, [token]);

  useEffect(() => { loadStats(); }, [loadStats]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#F8FAFB]">

      {/* Sidebar */}
      <aside className="w-60 shrink-0 bg-[#08292F] flex flex-col h-full">
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-emerald-500 rounded-xl flex items-center justify-center">
              <Shield size={15} className="text-white" />
            </div>
            <div>
              <p className="text-[14px] font-black text-white leading-none">Sylithe</p>
              <p className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">Admin Panel</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV.map(({ key, label, icon: Icon }) => {
            const active = section === key;
            const badge  = key === 'requests' && pendingCount > 0 ? pendingCount : null;
            return (
              <button key={key} onClick={() => setSection(key)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-[13px] font-semibold transition-colors text-left ${
                  active ? 'bg-white/15 text-white' : 'text-gray-400 hover:text-white hover:bg-white/10'
                }`}>
                <Icon size={15} className={active ? 'text-emerald-400' : ''} />
                <span className="flex-1">{label}</span>
                {badge && (
                  <span className="w-5 h-5 rounded-full bg-rose-500 text-white text-[10px] font-black flex items-center justify-center">
                    {badge > 9 ? '9+' : badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="px-4 py-4 border-t border-white/10">
          <div className="flex items-center gap-2.5 mb-3">
            <Avatar name={user?.fullName} email={user?.email} />
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-semibold text-white truncate">{user?.fullName || 'Admin'}</p>
              <p className="text-[10px] text-gray-400 truncate">{user?.email}</p>
            </div>
          </div>
          <button onClick={() => { logout(); navigate('/login'); }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-[15px] font-black text-[#0F172A]">{NAV.find(n => n.key === section)?.label}</h1>
            <p className="text-[11px] text-gray-400">Sylithe Platform Admin</p>
          </div>
          <button onClick={loadStats}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-[12px] text-gray-500 hover:bg-gray-50 transition-colors">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        <div className="p-8">
          {section === 'overview'   && <Overview stats={stats} recentUsers={recentUsers} recentRequests={recentReqs} onNav={setSection} />}
          {section === 'requests'   && <AccessRequests token={token} />}
          {section === 'projects'   && <ProjectsSection token={token} />}
          {section === 'users'      && <UsersSection token={token} />}
          {section === 'scans'      && <ScansSection token={token} />}
          {section === 'newsletter' && <NewsletterSection token={token} />}
        </div>
      </main>

    </div>
  );
}
