import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Send, Sparkles, Wrench, Plus } from 'lucide-react';
import { api } from '../api';
import { ErrorNote, useEvidence, cx } from '../ui';

const EXAMPLES = [
  'Analyze Reliance Industries’ Scope 1 and Scope 2 emissions trend.',
  'Which researched companies have the highest renewable-energy share?',
  'Compare three forestry projects in India.',
  'Find Gold Standard cookstove projects in India and explain the methodology risk.',
  'Why is additionality unknown for this project? Show the source.',
];

// Minimal, safe markdown: headings, bold, lists, tables, and clickable [ev_…] citations.
function Markdown({ text }) {
  const open = useEvidence();
  const inline = (s, key) => {
    const parts = s.split(/(\[ev_[0-9a-f]{16}\]|\*\*[^*]+\*\*)/g);
    return parts.map((p, i) => {
      const ev = p.match(/^\[(ev_[0-9a-f]{16})\]$/);
      if (ev) return <button key={`${key}-${i}`} onClick={() => open(ev[1])} className="mx-0.5 px-1 rounded bg-yellow-100 text-[10px] font-mono text-yellow-900 hover:bg-yellow-200 align-middle">source</button>;
      if (p.startsWith('**')) return <strong key={`${key}-${i}`}>{p.slice(2, -2)}</strong>;
      return <React.Fragment key={`${key}-${i}`}>{p}</React.Fragment>;
    });
  };
  const lines = text.split('\n');
  const out = [];
  for (let i = 0; i < lines.length; i += 1) {
    const l = lines[i];
    if (l.startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith('|')) { rows.push(lines[i]); i += 1; }
      i -= 1;
      const cells = rows.filter((r) => !/^\|\s*-/.test(r)).map((r) => r.split('|').slice(1, -1).map((c) => c.trim()));
      out.push(
        <div key={i} className="overflow-x-auto my-2"><table className="text-[13px] border border-slate-200">
          <thead className="bg-slate-50"><tr>{cells[0].map((c, j) => <th key={j} className="px-2 py-1 text-left border-b border-slate-200">{inline(c, `h${i}${j}`)}</th>)}</tr></thead>
          <tbody>{cells.slice(1).map((r, ri) => <tr key={ri} className="border-t border-slate-100">{r.map((c, j) => <td key={j} className="px-2 py-1">{inline(c, `c${i}${ri}${j}`)}</td>)}</tr>)}</tbody>
        </table></div>,
      );
    } else if (/^#{1,3} /.test(l)) {
      out.push(<div key={i} className="font-semibold text-slate-900 mt-3 mb-1">{inline(l.replace(/^#+ /, ''), i)}</div>);
    } else if (/^\s*[-*] /.test(l)) {
      out.push(<div key={i} className="flex gap-2 pl-1"><span>•</span><span>{inline(l.replace(/^\s*[-*] /, ''), i)}</span></div>);
    } else if (l.trim()) {
      out.push(<p key={i} className="my-1">{inline(l, i)}</p>);
    }
  }
  return <div className="text-[14px] leading-relaxed text-slate-800">{out}</div>;
}

// Reveals a finished answer progressively — medium-fast, a couple of words per frame —
// so it reads like the agent is writing it. Tokens are split on whitespace so
// markdown and [ev_…] citation markers are never cut in half.
const WORDS_PER_TICK = 2;
const TICK_MS = 30;

function TypedAnswer({ text, onProgress, onDone }) {
  const tokens = React.useMemo(() => text.split(/(\s+)/), [text]);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (n >= tokens.length) { onDone?.(); return undefined; }
    const t = setTimeout(() => { setN((x) => Math.min(tokens.length, x + WORDS_PER_TICK * 2)); onProgress?.(); }, TICK_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n, tokens.length]);
  const done = n >= tokens.length;
  return (
    <div>
      <Markdown text={tokens.slice(0, n).join('')} />
      {!done && <span className="inline-block w-2 h-4 align-middle bg-[#08292f] animate-pulse ml-0.5" />}
    </div>
  );
}

export default function Research() {
  const [params] = useSearchParams();
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [sessions, setSessions] = useState([]);
  const end = useRef(null);
  const asked = useRef(false);

  const loadSessions = () => api.sessions().then((d) => setSessions(d.sessions)).catch(() => {});
  useEffect(() => { loadSessions(); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);

  const send = async (text) => {
    const question = (text ?? q).trim();
    if (!question || busy) return;
    setQ(''); setErr(null); setBusy(true);
    setMessages((m) => [...m, { role: 'user', content: question }]);
    try {
      const r = await api.ask(question, sessionId);
      setSessionId(r.session_id);
      setMessages((m) => [...m, { role: 'assistant', content: r.answer, tools: r.tools_used, unverified: r.unverified_citations, cost: r.cost_usd, typing: true }]);
      loadSessions();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  useEffect(() => {
    const initial = params.get('q');
    if (initial && !asked.current) { asked.current = true; send(initial); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const openSession = (id) => api.session(id).then((s) => { setSessionId(s.id); setMessages(s.messages); });

  return (
    <div className="grid lg:grid-cols-[220px_1fr] gap-4 h-[calc(100vh-120px)]">
      <aside className="hidden lg:flex flex-col bg-white border border-slate-200 rounded-lg overflow-hidden">
        <button onClick={() => { setSessionId(null); setMessages([]); }} className="m-2 inline-flex items-center justify-center gap-1 text-sm border border-slate-300 rounded py-1.5 hover:bg-slate-50"><Plus className="w-4 h-4" /> New session</button>
        <div className="px-3 text-[10px] uppercase tracking-wider text-slate-400">Sessions</div>
        <ul className="flex-1 overflow-y-auto text-[13px]">
          {sessions.map((s) => (
            <li key={s.id}><button onClick={() => openSession(s.id)} className={cx('w-full text-left px-3 py-1.5 truncate hover:bg-slate-50', s.id === sessionId && 'bg-slate-100 font-medium')}>{s.title}</button></li>
          ))}
        </ul>
      </aside>
      <section className="flex flex-col bg-white border border-slate-200 rounded-lg overflow-hidden min-h-[500px]">
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {messages.length === 0 && (
            <div className="max-w-2xl mx-auto text-center pt-8">
              <Sparkles className="w-8 h-8 text-[#08292f] mx-auto" />
              <h1 className="text-lg font-semibold mt-2">Sylithe Research Agent</h1>
              <p className="text-sm text-slate-500 mt-1">Answers only from Sylithe's evidence-backed company and project data. Every number links to its source. Follow-up questions keep context.</p>
              <div className="mt-5 grid gap-2">
                {EXAMPLES.map((e) => <button key={e} onClick={() => send(e)} className="text-left text-sm border border-slate-200 rounded px-3 py-2 hover:bg-slate-50">{e}</button>)}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={cx('max-w-3xl', m.role === 'user' ? 'ml-auto' : '')}>
              {m.role === 'user' ? (
                <div className="bg-[#08292f] text-white text-sm rounded-lg px-3.5 py-2 inline-block float-right">{m.content}</div>
              ) : (
                <div className="border border-slate-200 rounded-lg p-4 clear-both">
                  {m.typing ? (
                    <TypedAnswer text={m.content}
                                 onProgress={() => end.current?.scrollIntoView({ block: 'end' })}
                                 onDone={() => setMessages((all) => all.map((x, j) => (j === i ? { ...x, typing: false } : x)))} />
                  ) : <Markdown text={m.content} />}
                  {!m.typing && (m.tools || []).length > 0 && (
                    <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-400 flex flex-wrap gap-x-3 gap-y-1">
                      <Wrench className="w-3 h-3" />
                      {m.tools.map((t, j) => <span key={j} className="font-mono">{t.tool}({Object.values(t.args || {}).join(', ')})</span>)}
                      {m.cost != null && <span>· ${Number(m.cost).toFixed(4)}</span>}
                    </div>
                  )}
                  {(m.unverified || m.unverified_citations || []).length > 0 && <div className="text-[11px] text-rose-600 mt-1">Warning: {(m.unverified || m.unverified_citations).length} citation(s) could not be matched to stored evidence.</div>}
                </div>
              )}
              <div className="clear-both" />
            </div>
          ))}
          {busy && <div className="text-sm text-slate-500 flex items-center gap-2"><Sparkles className="w-4 h-4 animate-pulse" /> Agent is querying Sylithe data…</div>}
          <ErrorNote error={err} />
          <div ref={end} />
        </div>
        <div className="border-t border-slate-200 p-3 flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} placeholder="Ask about a company's emissions, a project's rating, comparisons…"
                 className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm outline-none focus:border-[#08292f]" />
          <button onClick={() => send()} disabled={busy || !q.trim()} className="bg-[#08292f] text-white rounded-md px-3 disabled:opacity-40"><Send className="w-4 h-4" /></button>
        </div>
      </section>
    </div>
  );
}
