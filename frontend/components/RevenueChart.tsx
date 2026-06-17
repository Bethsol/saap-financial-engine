"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";

type Point = { month: string; revenue: number; expenses: number; net: number };

export default function RevenueChart({ series }: { series: Point[] }) {
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={series}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(v: number) =>
              v.toLocaleString(undefined, { maximumFractionDigits: 0 })
            }
          />
          <Legend />
          <Bar dataKey="revenue"  name="Revenue"  fill="#2563eb" />
          <Bar dataKey="expenses" name="Expenses" fill="#f97316" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
