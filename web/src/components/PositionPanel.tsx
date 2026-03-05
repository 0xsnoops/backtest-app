"use client";

import { Snapshot } from "@/lib/store";

interface PositionPanelProps {
  snapshot: Snapshot | null;
  startingCapital: number;
}

export default function PositionPanel({ snapshot, startingCapital }: PositionPanelProps) {
  if (!snapshot) {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-300 uppercase mb-2">Position</h3>
        <p className="text-gray-500 text-sm">No data yet</p>
      </div>
    );
  }

  const totalPnl = snapshot.equity - startingCapital;
  const pnlPct = (totalPnl / startingCapital) * 100;

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-2">
      <h3 className="text-sm font-semibold text-gray-300 uppercase">Position</h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-400">Equity</span>
          <p className="text-white font-mono">${snapshot.equity.toFixed(2)}</p>
        </div>
        <div>
          <span className="text-gray-400">Cash</span>
          <p className="text-white font-mono">${snapshot.cash.toFixed(2)}</p>
        </div>
        <div>
          <span className="text-gray-400">Position</span>
          <p className={`font-mono ${snapshot.position_qty > 0 ? "text-green-400" : snapshot.position_qty < 0 ? "text-red-400" : "text-white"}`}>
            {snapshot.position_qty.toFixed(4)}
          </p>
        </div>
        <div>
          <span className="text-gray-400">Avg Price</span>
          <p className="text-white font-mono">${snapshot.avg_price.toFixed(2)}</p>
        </div>
        <div>
          <span className="text-gray-400">Unrealized P&L</span>
          <p className={`font-mono ${snapshot.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
            ${snapshot.unrealized_pnl.toFixed(2)}
          </p>
        </div>
        <div>
          <span className="text-gray-400">Realized P&L</span>
          <p className={`font-mono ${snapshot.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
            ${snapshot.realized_pnl.toFixed(2)}
          </p>
        </div>
      </div>
      <div className="border-t border-gray-700 pt-2">
        <span className="text-gray-400 text-sm">Total P&L</span>
        <p className={`font-mono text-lg ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
          ${totalPnl.toFixed(2)} ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)
        </p>
      </div>
    </div>
  );
}
