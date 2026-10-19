import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { getStats } from "../api";

const fmt = (v) => Number(v).toFixed(2);

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStats()
      .then(({ data }) => setStats(data))
      .catch(() => setError("Impossible de charger les statistiques."));
  }, []);

  if (error) return <p className="max-w-6xl mx-auto p-6 text-red-600">{error}</p>;
  if (!stats) return <p className="max-w-6xl mx-auto p-6 text-gray-400">Chargement...</p>;

  // Agregats calcules cote serveur, par devise : on n'additionne jamais EUR et USD.
  const currencies = stats.totals_by_currency;
  const mainCurrency = currencies.length
    ? currencies.reduce((a, b) => (b.count > a.count ? b : a)).currency
    : null;
  const chartData = stats.totals_by_supplier
    .filter((s) => s.currency === mainCurrency)
    .map((s) => ({ name: s.supplier_name, amount: s.amount_ttc, count: s.count }));

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Tableau de bord</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow-sm border p-4">
          <p className="text-sm text-gray-500">Total factures</p>
          <p className="text-2xl font-semibold">{stats.invoice_count}</p>
          <p className="text-xs text-gray-400">
            {stats.included_count} avec montant extrait
            {stats.needs_review_ids.length > 0 && ` · ${stats.needs_review_ids.length} a verifier`}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border p-4">
          <p className="text-sm text-gray-500">Montant total TTC</p>
          {currencies.length === 0 && <p className="text-2xl font-semibold">—</p>}
          {currencies.map((c) => (
            <p key={c.currency} className="text-2xl font-semibold">
              {fmt(c.amount_ttc)} <span className="text-base text-gray-500">{c.currency}</span>
            </p>
          ))}
          <p className="text-xs text-gray-400">Un total par devise</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border p-4">
          <p className="text-sm text-gray-500">Fournisseurs distincts</p>
          <p className="text-2xl font-semibold">{stats.distinct_suppliers}</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border p-4 h-96">
        <h2 className="font-semibold mb-4">
          Montant TTC par fournisseur {mainCurrency ? `(${mainCurrency})` : ""}
        </h2>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis />
            <Tooltip formatter={(v) => `${fmt(v)} ${mainCurrency || ""}`} />
            <Bar dataKey="amount" name="TTC" fill="#2563eb" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
