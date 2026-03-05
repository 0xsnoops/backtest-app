"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { CandleData } from "@/lib/store";

const Chart = dynamic(() => import("@/components/EquityCurveChart"), { ssr: false });

interface RoundMetric {
  round_number: number;
  pnl_dollar: number;
  pnl_pct: number;
  max_drawdown: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  num_trades: number;
  profit_factor: number;
  sharpe: number;
  equity_curve: number[];
}

interface SimMetrics {
  total_pnl_dollar: number;
  total_pnl_pct: number;
  total_trades: number;
  rounds: RoundMetric[];
}

export default function ResultsPage() {
  const router = useRouter();
  const params = useParams();
  const simId = params.simId as string;
  const [metrics, setMetrics] = useState<SimMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSimMetrics(simId).then(setMetrics).catch(() => {}).finally(() => setLoading(false));
  }, [simId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400">Loading results...</div>
      </div>
    );
  }

  if (!metrics || !metrics.rounds?.length) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <button onClick={() => router.push(`/simulation/${simId}`)} className="text-gray-400 hover:text-white text-sm">
          &larr; Back
        </button>
        <div className="bg-gray-800 rounded-xl p-8 mt-4 text-center">
          <p className="text-gray-400">No completed rounds yet. Complete some rounds first!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <button onClick={() => router.push(`/simulation/${simId}`)} className="text-gray-400 hover:text-white text-sm">
        &larr; Back to Rounds
      </button>

      <h1 className="text-2xl font-bold">Simulation Results</h1>

      <div className="bg-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-bold mb-4">Overall Summary</h2>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <span className="text-gray-400 text-sm">Total P&L</span>
            <p className={`text-2xl font-bold ${metrics.total_pnl_dollar >= 0 ? "text-green-400" : "text-red-400"}`}>
              ${metrics.total_pnl_dollar.toFixed(2)}
            </p>
            <p className={`text-sm ${metrics.total_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
              {metrics.total_pnl_pct >= 0 ? "+" : ""}{metrics.total_pnl_pct.toFixed(2)}%
            </p>
          </div>
          <div>
            <span className="text-gray-400 text-sm">Total Trades</span>
            <p className="text-2xl font-bold text-white">{metrics.total_trades}</p>
          </div>
          <div>
            <span className="text-gray-400 text-sm">Rounds Completed</span>
            <p className="text-2xl font-bold text-white">{metrics.rounds.length}</p>
          </div>
        </div>
      </div>

      {metrics.rounds.some(r => r.equity_curve?.length > 0) && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-bold mb-4">Combined Equity Curve</h2>
          <Chart rounds={metrics.rounds} />
        </div>
      )}

      <h2 className="text-lg font-bold">Per-Round Results</h2>
      <div className="grid gap-4">
        {metrics.rounds.map((rnd) => (
          <div key={rnd.round_number} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <div className="flex justify-between items-start mb-3">
              <h3 className="font-bold">Round {rnd.round_number}</h3>
              <span
                className={`text-lg font-bold ${rnd.pnl_dollar >= 0 ? "text-green-400" : "text-red-400"}`}
              >
                ${rnd.pnl_dollar.toFixed(2)} ({rnd.pnl_pct >= 0 ? "+" : ""}{rnd.pnl_pct.toFixed(2)}%)
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <span className="text-gray-400">Max Drawdown</span>
                <p className="text-red-400">{rnd.max_drawdown.toFixed(2)}%</p>
              </div>
              <div>
                <span className="text-gray-400">Win Rate</span>
                <p className="text-white">{rnd.win_rate.toFixed(1)}%</p>
              </div>
              <div>
                <span className="text-gray-400">Trades</span>
                <p className="text-white">{rnd.num_trades}</p>
              </div>
              <div>
                <span className="text-gray-400">Profit Factor</span>
                <p className="text-white">{rnd.profit_factor.toFixed(2)}</p>
              </div>
              <div>
                <span className="text-gray-400">Avg Win</span>
                <p className="text-green-400">${rnd.avg_win.toFixed(2)}</p>
              </div>
              <div>
                <span className="text-gray-400">Avg Loss</span>
                <p className="text-red-400">${rnd.avg_loss.toFixed(2)}</p>
              </div>
              <div>
                <span className="text-gray-400">Sharpe</span>
                <p className="text-white">{rnd.sharpe.toFixed(2)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
