import type { LucideIcon } from "lucide-react";

type Props = {
  label: string;
  value: number;
  currency?: string;
  suffix?: string;
  trend?: number;
  invertTrend?: boolean;
  Icon: LucideIcon;
  highlight?: boolean;
};

export default function KPICard({
  label, value, currency, suffix, trend, invertTrend, Icon, highlight,
}: Props) {
  const trendColor =
    trend === undefined
      ? "text-slate-400"
      : (invertTrend ? trend < 0 : trend >= 0)
        ? "text-emerald-600"
        : "text-rose-600";

  return (
    <div
      className={
        "rounded-xl border p-5 " +
        (highlight
          ? "border-brand-500 bg-brand-50"
          : "border-slate-200 bg-white")
      }
    >
      <div className="flex items-start justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <Icon className="w-4 h-4 text-slate-400" />
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">
        {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        {suffix && <span className="text-lg ml-1">{suffix}</span>}
        {currency && <span className="text-sm text-slate-500 ml-2">{currency}</span>}
      </p>
      {trend !== undefined && (
        <p className={`text-xs mt-1 ${trendColor}`}>
          {trend >= 0 ? "▲" : "▼"} {Math.abs(trend).toFixed(1)}% vs prior period
        </p>
      )}
    </div>
  );
}
