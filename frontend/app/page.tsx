
"use client";
import { useEffect, useState, useRef } from "react";
import KPICard from "@/components/KPICard";
import RevenueChart from "@/components/RevenueChart";
import AIInsights from "@/components/AIInsights";
import { TrendingUp, TrendingDown, Wallet, Percent, Upload, FileText, X } from "lucide-react";
type Snapshot = { metrics: { period_start: string; period_end: string; base_currency: string; total_revenue: number; total_expenses: number; net_profit: number; profit_margin_pct: number; revenue_trend_pct: number; expense_trend_pct: number; monthly_burn: number; runway_months: number | null; expense_concentration_pct: number; revenue_by_category: { category: string; amount: number }[]; expenses_by_category: { category: string; amount: number }[]; monthly_series: { month: string; revenue: number; expenses: number; net: number }[]; }; insights: { headline: string; diagnosis: string; risks: string[]; recommendations: { action: string; rationale: string; horizon: string }[]; }; ingestion: { detected_mapping: Record<string, string>; source_system_hint: string; rows_in: number; rows_out: number; }; };
const SOURCES = [{ id: "ro_saga_export.csv", label: "Romania · SAGA (RON)" }, { id: "us_quickbooks.csv", label: "USA · QuickBooks (USD)" }, { id: "de_datev_export.csv", label: "Germany · DATEV (EUR)" }];
type Mode = "sample" | "upload";
export default function Dashboard() {
  const [mode, setMode] = useState<Mode>("sample");
  const [source, setSource] = useState(SOURCES[0].id);
  const [data, setData] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (mode !== "sample") return;
    const ctrl = new AbortController();
    setLoading(true); setErr(null); setData(null);
    fetch(`${process.env.NEXT_PUBLIC_API_BASE}/dashboard/sample?source=${source}`, { signal: ctrl.signal })
      .then(r => { if (!r.ok) throw new Error("API " + r.status); return r.json(); })
      .then(setData).catch(e => { if (e.name !== "AbortError") setErr(e.message); }).finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [source, mode]);
  const runUpload = async (file: File) => {
    setLoading(true); setErr(null); setData(null); setUploadedFile(file);
    try {
      const form = new FormData(); form.append("file", file);
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/ingest`, { method: "POST", body: form });
      if (!res.ok) throw new Error("API " + res.status);
      setData(await res.json());
    } catch (e: any) { setErr(e.message); } finally { setLoading(false); }
  };
  const clearUpload = () => { setUploadedFile(null); setData(null); setErr(null); if (fileRef.current) fileRef.current.value = ""; };
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end gap-3">
        <div><h2 className="text-2xl font-semibold">Client Dashboard</h2><p className="text-sm text-slate-500">Agnostic pipeline · SAGA, QuickBooks, DATEV</p></div>
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-sm">
          <button onClick={() => { setMode("sample"); setData(null); clearUpload(); }} className={`px-4 py-2 ${mode === "sample" ? "bg-blue-600 text-white" : "bg-white text-slate-600"}`}>Sample data</button>
          <button onClick={() => { setMode("upload"); setData(null); }} className={`px-4 py-2 ${mode === "upload" ? "bg-blue-600 text-white" : "bg-white text-slate-600"}`}>Upload your file</button>
        </div>
      </div>
      {mode === "sample" && <select value={source} onChange={e => setSource(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">{SOURCES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>}
      {mode === "upload" && !uploadedFile && <div onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) runUpload(f); }} onClick={() => fileRef.current?.click()} className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center ${dragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white"}`}><Upload className="mx-auto mb-3 h-8 w-8 text-slate-400" /><p className="font-medium">Drop your CSV file here</p><p className="text-sm text-slate-500 mt-1">or click to browse</p><input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) runUpload(f); }} /></div>}
      {mode === "upload" && uploadedFile && !loading && <div className="flex items-center gap-3 rounded-lg border bg-white px-4 py-3 text-sm"><FileText className="h-4 w-4 text-blue-600" /><span>{uploadedFile.name}</span><button onClick={clearUpload} className="ml-auto"><X className="h-4 w-4" /></button></div>}
      {loading && <div className="flex items-center gap-3 text-sm text-slate-500"><div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />Running pipeline…</div>}
      {err && <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">Error: {err}</div>}
      {data && <>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard label="Total Revenue" value={data.metrics.total_revenue} currency={data.metrics.base_currency} trend={data.metrics.revenue_trend_pct} Icon={TrendingUp} />
          <KPICard label="Total Expenses" value={data.metrics.total_expenses} currency={data.metrics.base_currency} trend={data.metrics.expense_trend_pct} invertTrend Icon={TrendingDown} />
          <KPICard label="Net Profit" value={data.metrics.net_profit} currency={data.metrics.base_currency} Icon={Wallet} highlight />
          <KPICard label="Profit Margin" value={data.metrics.profit_margin_pct} suffix="%" Icon={Percent} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 rounded-xl border bg-white p-5"><h3 className="font-medium mb-3">Revenue vs Expenses</h3><RevenueChart series={data.metrics.monthly_series} /></div>
          <AIInsights insights={data.insights} />
        </div>
      </>}
    </div>
  );
}
