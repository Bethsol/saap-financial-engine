import { Brain, AlertTriangle, Target } from "lucide-react";

type Props = {
  insights: {
    headline: string;
    diagnosis: string;
    risks: string[];
    recommendations: { action: string; rationale: string; horizon: string }[];
  };
};

export default function AIInsights({ insights }: Props) {
  return (
    <div className="rounded-xl border border-brand-500 bg-brand-50 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-brand-700" />
        <h3 className="font-medium text-brand-900">AI CFO Insights</h3>
      </div>

      <p className="text-sm font-medium text-brand-900">{insights.headline}</p>
      <p className="text-sm text-slate-600 mt-2">{insights.diagnosis}</p>

      <div className="mt-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-rose-700">
          <AlertTriangle className="w-3 h-3" /> Risks
        </div>
        <ul className="mt-1 space-y-1">
          {insights.risks.map((r, i) => (
            <li key={i} className="text-sm text-slate-700">• {r}</li>
          ))}
        </ul>
      </div>

      <div className="mt-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-emerald-700">
          <Target className="w-3 h-3" /> Recommendations
        </div>
        <ul className="mt-1 space-y-2">
          {insights.recommendations.map((r, i) => (
            <li key={i} className="text-sm">
              <p className="font-medium text-slate-800">{r.action}</p>
              <p className="text-xs text-slate-600">
                {r.rationale} <span className="italic">· {r.horizon}</span>
              </p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
