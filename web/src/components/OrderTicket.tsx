"use client";

import { useState } from "react";

interface OrderTicketProps {
  onSubmit: (order: {
    side: string;
    type: string;
    qty: number;
    limit_price: number | null;
  }) => void;
  disabled?: boolean;
  currentPrice?: number;
}

export default function OrderTicket({ onSubmit, disabled, currentPrice }: OrderTicketProps) {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [type, setType] = useState<"market" | "limit">("market");
  const [qty, setQty] = useState("1");
  const [limitPrice, setLimitPrice] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = parseFloat(qty);
    if (isNaN(q) || q <= 0) return;
    onSubmit({
      side,
      type,
      qty: q,
      limit_price: type === "limit" ? parseFloat(limitPrice) : null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-800 rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-300 uppercase">Order Ticket</h3>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setSide("buy")}
          className={`py-2 rounded font-bold text-sm ${
            side === "buy"
              ? "bg-green-600 text-white"
              : "bg-gray-700 text-gray-400"
          }`}
        >
          BUY
        </button>
        <button
          type="button"
          onClick={() => setSide("sell")}
          className={`py-2 rounded font-bold text-sm ${
            side === "sell"
              ? "bg-red-600 text-white"
              : "bg-gray-700 text-gray-400"
          }`}
        >
          SELL
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setType("market")}
          className={`py-1.5 rounded text-xs ${
            type === "market"
              ? "bg-blue-600 text-white"
              : "bg-gray-700 text-gray-400"
          }`}
        >
          Market
        </button>
        <button
          type="button"
          onClick={() => setType("limit")}
          className={`py-1.5 rounded text-xs ${
            type === "limit"
              ? "bg-blue-600 text-white"
              : "bg-gray-700 text-gray-400"
          }`}
        >
          Limit
        </button>
      </div>

      <div>
        <label className="text-xs text-gray-400">Quantity</label>
        <input
          type="number"
          step="any"
          min="0"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white text-sm"
        />
      </div>

      {type === "limit" && (
        <div>
          <label className="text-xs text-gray-400">Limit Price</label>
          <input
            type="number"
            step="any"
            min="0"
            value={limitPrice}
            onChange={(e) => setLimitPrice(e.target.value)}
            placeholder={currentPrice?.toFixed(2)}
            className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white text-sm"
          />
        </div>
      )}

      {currentPrice && (
        <div className="text-xs text-gray-500">
          Current price: ${currentPrice.toFixed(2)}
        </div>
      )}

      <button
        type="submit"
        disabled={disabled}
        className={`w-full py-2 rounded font-bold text-sm ${
          disabled
            ? "bg-gray-600 text-gray-400 cursor-not-allowed"
            : side === "buy"
            ? "bg-green-600 hover:bg-green-500 text-white"
            : "bg-red-600 hover:bg-red-500 text-white"
        }`}
      >
        {disabled ? "Round Finished" : `${side.toUpperCase()} ${qty}`}
      </button>
    </form>
  );
}
