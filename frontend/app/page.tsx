"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import KPICard from "@/components/KPICard";
import RevenueChart from "@/components/RevenueChart";
import AIInsights from "@/components/AIInsights";
import { TrendingUp, TrendingDown, Wallet, Percent, Upload, FileText, X, LogOut } from "lucide-react";

type Snapshot = {
  metrics: {
    period_start: string;
    period_end: string;
    base_currency: string;
    total_revenue: number;
    total_expenses: number;
    net_profit: number;
    profit_margin_pct: number;
    revenue_trend_pct: number;
    expense_trend_pct: number;
    monthly_burn: number;
    runway_months: number | null;
    expense_concentration_pct: number;
    revenue_by_category: { category: string; amount: number }[];
    expenses_by_category: { category: string; amount: number }[];
    monthly_series: { month: string; revenue: number; expenses: number; net: number }[];
  };
  insights: {
    headline: string;
    diagnosis: string;
    risks: string[];
    recommendations: { action: string; rationale: string; horizon: string }[];
  };
  ingestion: {
    detected_mapping: Record<string, string>;
    source_system_hint: string;
    rows_in: number;
    rows_out: number;
  };
};

const SOURCES = [
  { id: "ro_saga_export.csv",  label: "Romania · SAGA (RON)" },
  { id: "us_quickbooks.csv",   label: "USA · QuickBooks (USD)" },
  { id: "de_datev_export.csv", label: "Germany · DATEV (EUR)" },
];

type Mode = "sample" | "upload";

function authHeaders() {
  const token = typeof window !== "undefined" ? localStorage.getItem("saap_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : ({} as Record<string, string>);
}

export default function Dashboard() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [mode, setMode] = useState<Mode>("sample");
  const [source, setSource] = useState(SOURCES[0].id);
  const [data, setData] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Auth guard
  useEffect(() => {
    const token = localStorage.getItem("saap_token");
    if (!token) {
      router.push("/login");
      return;
    }
    setUserEmail(localStorage.getItem("saap_email") || "");
    setReady(true);
  }, [router]);

  useEffect(() => {
    if (!ready || mode !== "sample") return;
    const ctrl = new AbortController();
    setLoading(true);
    setErr(null);
    setData(null);
    fetch(`${process.env.NEXT_PUBLIC_API_BASE}/dashboard/sample?source=${source}`, {
      signal: ctrl.signal,
      headers: authHeaders(),
    })
      .then((r) => {
        if (r.status === 401) { logout(); throw new Error("Session expired."); }
        if (!r.ok) throw new Error(`API ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => { if (e.name !== "AbortError") setErr(e.message); })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [source, mode, ready]);

  const runUpload = async (file: File) => {
    setLoading(true);
    setErr(null);
    setData(null);
    setUploadedFile(file);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/ingest`, {
        method: "POST",
        body: form,
        headers: authHeaders(),
      });
      if (res.status === 401) { logout(); return; }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API ${res.status}: ${text}`);
      }
      setData(await res.json());
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("saap_token");
    localStorage.removeItem("saap_email");
    localStorage.removeItem("saap_full_name");
    router.push("/login");
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) runUpload(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.name.endsWith(".csv")) runUpload(file);
  };

  const clearUpload = () => {
    setUploadedFile(null);
    setData(null);
    setErr(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  if (!ready) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Client Dashboard</h2>
          <p className="text-sm text-slate-500">
            Agnostic pipeline · supports SAGA, QuickBooks, DATEV and more.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{userEmail}</span>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            <LogOut className="h-3.5 w-3.5" /> Log out
          </button>
        </div>
      </div>

      <div className="flex rounded-lg border border-slate-200 overflow-hidden text-sm w-fit">
        <button
          onClick={() => { setMode("sample"); setData(null); clearUpload(); }}
          className={`px-4 py-2 ${mode === "sample" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >
          Sample data
        </button>
        <button
          onClick={() => { setMode("upload"); setData(null); }}
          className={`px-4 py-2 ${mode === "upload" ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >
          Upload your file
        </button>
      </div>

      {mode === "sample" && (
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
        >
          {SOURCES.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
      )}

      {mode === "upload" && !uploadedFile && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
            dragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white hover:border-blue-400 hover:bg-slate-50"
          }`}
        >
          <Upload className="mx-auto mb-3 h-8 w-8 text-slate-400" />
          <p className="font-medium text-slate-700">Drop your CSV file here</p>
          <p className="text-sm text-slate-500 mt-1">
            or click to browse · supports SAGA, QuickBooks, DATEV exports
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      )}

      {mode === "upload" && uploadedFile && !loading && (
        <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
          <FileText className="h-4 w-4 text-blue-600" />
          <span className="font-medium">{uploadedFile.name}</span>
          <span className="text-slate-400">·</span>
          <span className="text-slate-500">{(uploadedFile.size / 1024).toFixed(1)} KB</span>
          <button onClick={clearUpload} className="ml-auto text-slate-400 hover:text-slate-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          Running pipeline…
        </div>
      )}

      {err && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {err}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard label="Total Revenue" value={data.metrics.total_revenue} currency={data.metrics.base_currency} trend={data.metrics.revenue_trend_pct} Icon={TrendingUp} />
            <KPICard label="Total Expenses" value={data.metrics.total_expenses} currency={data.metrics.base_currency} trend={data.metrics.expense_trend_pct} invertTrend Icon={TrendingDown} />
            <KPICard label="Net Profit" value={data.metrics.net_profit} currency={data.metrics.base_currency} Icon={Wallet} highlight />
            <KPICard label="Profit Margin" value={data.metrics.profit_margin_pct} suffix="%" Icon={Percent} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="font-medium mb-3">Revenue vs Expenses · monthly</h3>
              <RevenueChart series={data.metrics.monthly_series} />
            </div>
            <AIInsights insights={data.insights} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CategoryBreakdown title="Revenue by category" rows={data.metrics.revenue_by_category} currency={data.metrics.base_currency} />
            <CategoryBreakdown title="Expenses by category" rows={data.metrics.expenses_by_category} currency={data.metrics.base_currency} />
          </div>

          <details className="rounded-xl border border-slate-200 bg-white p-5 text-sm">
            <summary className="cursor-pointer font-medium">Ingestion audit · how the engine read your file</summary>
            <div className="mt-3 space-y-2 text-slate-600">
              <p>Source: <code>{data.ingestion.source_system_hint}</code></p>
              <p>Rows in: {data.ingestion.rows_in} → Rows out: {data.ingestion.rows_out}</p>
              <p className="font-medium pt-2">Detected column mapping:</p>
              <ul className="list-disc pl-6">
                {Object.entries(data.ingestion.detected_mapping).map(([k, v]) => (
                  <li key={k}><code>{k}</code> ← <code>{v}</code></li>
                ))}
              </ul>
            </div>
          </details>
        </>
      )}
    </div>
  );
}

function CategoryBreakdown({ title, rows, currency }: { title: string; rows: { category: string; amount: number }[]; currency: string; }) {
  const total = rows.reduce((acc, r) => acc + r.amount, 0) || 1;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="font-medium mb-3">{title}</h3>
      <ul className="space-y-2">
        {rows.map((r) => {
          const share = (r.amount / total) * 100;
          return (
            <li key={r.category}>
              <div className="flex justify-between text-sm">
                <span>{r.category}</span>
                <span className="font-medium">{r.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })} {currency}</span>
              </div>
              <div className="h-1.5 mt-1 rounded bg-slate-100 overflow-hidden">
                <div className="h-full bg-blue-500" style={{ width: `${Math.min(share, 100)}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
