"use client";

import { FillData, OrderData } from "@/lib/store";

interface TradeLogProps {
  fills: FillData[];
  orders: OrderData[];
}

export default function TradeLog({ fills, orders }: TradeLogProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-300 uppercase mb-2">Trade Log</h3>
      {fills.length === 0 ? (
        <p className="text-gray-500 text-sm">No trades yet</p>
      ) : (
        <div className="max-h-48 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-700">
                <th className="text-left py-1">Side</th>
                <th className="text-right py-1">Qty</th>
                <th className="text-right py-1">Price</th>
                <th className="text-right py-1">Fee</th>
                <th className="text-right py-1">Index</th>
              </tr>
            </thead>
            <tbody>
              {fills.map((f, i) => (
                <tr key={i} className="border-b border-gray-700/50">
                  <td className={`py-1 font-bold ${f.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                    {f.side.toUpperCase()}
                  </td>
                  <td className="text-right text-white py-1">{f.qty}</td>
                  <td className="text-right text-white py-1">${f.fill_price.toFixed(2)}</td>
                  <td className="text-right text-gray-400 py-1">${f.fee.toFixed(4)}</td>
                  <td className="text-right text-gray-400 py-1">{f.ts_index}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
