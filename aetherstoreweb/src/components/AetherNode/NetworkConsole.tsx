import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Trash2, Pause, Play, Download } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { aetherNodeApi, createAuthenticatedClient } from '../../services/api';

interface LogEntry {
    id: number;
    ts: string;
    level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG' | 'SYS';
    source: string;
    message: string;
}



const LEVEL_COLOR: Record<string, string> = {
    INFO: '#10b981', WARN: '#f59e0b', ERROR: '#ef4444', DEBUG: '#64748b', SYS: '#6366f1',
};

export const NetworkConsole: React.FC = () => {
    const { did } = useAuthStore();
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [paused, setPaused] = useState(false);
    const [filter, setFilter] = useState<LogEntry['level'] | 'ALL'>('ALL');
    const [search, setSearch] = useState('');
    const bottomRef = useRef<HTMLDivElement>(null);
    const autoScroll = useRef(true);

    const fetchLogs = async () => {
        if (paused) return;
        try {
            const client = createAuthenticatedClient(did);
            const r = await aetherNodeApi.getSystemLogs(client, 150);
            
            // Map string logs to LogEntry structure
            const realLogs: LogEntry[] = r.data.logs.map((raw, idx) => {
                // Parse: 2026-03-09 14:22:53,456 [INFO] apps.p2p.views: Message here
                const parts = raw.match(/^([\d-]+\s[\d:,]+)\s\[(\w+)\]\s([\w\s.]+):\s(.*)$/);
                if (parts) {
                    return {
                        id: idx,
                        ts: parts[1],
                        level: parts[2] as any,
                        source: parts[3],
                        message: parts[4]
                    };
                }
                return { id: idx, ts: '', level: 'INFO', source: 'system', message: raw };
            });
            
            setLogs(realLogs);
        } catch (e) {
            console.error('Failed to fetch system logs', e);
        }
    };

    useEffect(() => {
        fetchLogs();
        const iv = setInterval(fetchLogs, 3000);
        return () => clearInterval(iv);
    }, [paused, did]);

    useEffect(() => {
        if (autoScroll.current) {
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs]);

    const filtered = logs.filter(l =>
        (filter === 'ALL' || l.level === filter) &&
        (!search || l.message.toLowerCase().includes(search.toLowerCase()) || l.source.includes(search.toLowerCase()))
    );

    const exportLogs = () => {
        const text = filtered.map(l => `[${l.ts}] [${l.level}] [${l.source}] ${l.message}`).join('\n');
        const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
        const a = document.createElement('a'); a.href = url; a.download = 'aethernode-console.log'; a.click();
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 220px)', minHeight: 500 }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '0.4rem 0.75rem', flex: 1, minWidth: 200 }}>
                    <Terminal size={14} color="var(--text-muted)" />
                    <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter logs..."
                        style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary)', fontSize: '0.85rem', flex: 1, fontFamily: 'monospace' }} />
                </div>

                {/* Level filter */}
                <div style={{ display: 'flex', gap: '0.375rem' }}>
                    {(['ALL', 'INFO', 'WARN', 'ERROR', 'DEBUG', 'SYS'] as const).map(l => (
                        <button key={l} onClick={() => setFilter(l)}
                            style={{
                                padding: '0.375rem 0.75rem', borderRadius: 6, border: '1px solid',
                                borderColor: filter === l ? (LEVEL_COLOR[l] ?? 'var(--accent-primary)') : 'var(--border-color)',
                                background: filter === l ? `${(LEVEL_COLOR[l] ?? 'var(--accent-primary)')}15` : 'transparent',
                                color: filter === l ? (LEVEL_COLOR[l] ?? 'var(--accent-primary)') : 'var(--text-muted)',
                                fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer',
                            }}>{l}</button>
                    ))}
                </div>

                <button onClick={() => setPaused(p => !p)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.5rem 0.875rem', borderRadius: 8, border: '1px solid var(--border-color)', background: 'transparent', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: paused ? '#10b981' : 'var(--text-muted)' }}>
                    {paused ? <><Play size={14} /> Resume</> : <><Pause size={14} /> Pause</>}
                </button>

                <button onClick={() => setLogs([])}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.5rem 0.75rem', borderRadius: 8, border: '1px solid var(--border-color)', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
                    <Trash2 size={14} /> Clear
                </button>

                <button onClick={exportLogs}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.5rem 0.75rem', borderRadius: 8, border: '1px solid var(--border-color)', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
                    <Download size={14} /> Export
                </button>
            </div>

            {/* Terminal */}
            <div
                onScroll={e => { const el = e.currentTarget; autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40; }}
                style={{ flex: 1, overflowY: 'auto', background: '#0d1117', border: '1px solid var(--border-color)', borderRadius: 10, padding: '1rem 1.25rem', fontFamily: 'monospace', fontSize: '0.82rem' }}
            >
                {/* Live indicator */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.875rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    {!paused && <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981', animation: 'pulse 1.5s infinite', flexShrink: 0 }} />}
                    <span style={{ color: '#475569', fontSize: '0.75rem' }}>
                        {paused ? '⏸ PAUSED —' : '● LIVE —'} AetherNode Network Console · {filtered.length} entries
                    </span>
                </div>

                {filtered.length === 0 ? (
                    <span style={{ color: '#475569' }}>No log entries match the current filter.</span>
                ) : (
                    filtered.map(log => (
                        <div key={log.id} style={{ display: 'flex', gap: '0.75rem', lineHeight: 1.6, marginBottom: 2 }}>
                            <span style={{ color: '#334155', minWidth: 148, flexShrink: 0 }}>{log.ts}</span>
                            <span style={{ minWidth: 44, fontWeight: 800, color: LEVEL_COLOR[log.level] ?? '#94a3b8', flexShrink: 0 }}>{log.level}</span>
                            <span style={{ minWidth: 110, color: '#6366f1', flexShrink: 0, opacity: 0.85 }}>[{log.source}]</span>
                            <span style={{ color: '#cbd5e1', wordBreak: 'break-word' }}>{log.message}</span>
                        </div>
                    ))
                )}
                <div ref={bottomRef} />
            </div>

            {/* Footer status */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.625rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                <span>{logs.length} total entries · {filtered.length} visible</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: paused ? '#f59e0b' : '#10b981', display: 'inline-block' }} />
                    {paused ? 'Stream paused' : 'Streaming live'}
                </span>
            </div>
        </div>
    );
};
