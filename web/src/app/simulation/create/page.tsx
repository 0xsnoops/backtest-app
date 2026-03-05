"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function CreateSimulationPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [market, setMarket] = useState("crypto");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [numRounds, setNumRounds] = useState(5);
  const [startingCapital, setStartingCapital] = useState(10000);
  const [feeBps, setFeeBps] = useState(10);
  const [slippageBps, setSlippageBps] = useState(5);
  const [sessionFilter, setSessionFilter] = useState<string>("");
  const [sessionStart, setSessionStart] = useState("09:30");
  const [sessionEnd, setSessionEnd] = useState("16:00");

  const symbols: Record<string, string[]> = {
    crypto: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const sim = await api.createSimulation({
        market,
        symbol,
        timeframe: "1m",
        session_filter: sessionFilter || null,
        session_start: sessionFilter === "custom" ? sessionStart : null,
        session_end: sessionFilter === "custom" ? sessionEnd : null,
        num_rounds: numRounds,
        starting_capital: startingCapital,
        fee_bps: feeBps,
        slippage_bps: slippageBps,
      });
      router.push(`/simulation/${sim.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create simulation");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <button
        onClick={() => router.push("/dashboard")}
        className="text-gray-400 hover:text-white text-sm mb-4"
      >
        &larr; Back to Dashboard
      </button>

      <h1 className="text-2xl font-bold mb-6">Create Simulation</h1>

      <form onSubmit={handleSubmit} className="bg-gray-800 rounded-xl p-6 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Market</label>
            <select
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
            >
              <option value="crypto">Crypto</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Symbol</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
            >
              {(symbols[market] || []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Number of Rounds</label>
            <select
              value={numRounds}
              onChange={(e) => setNumRounds(parseInt(e.target.value))}
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
            >
              {[3, 5, 10, 15, 25].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Starting Capital ($)</label>
            <input
              type="number"
              value={startingCapital}
              onChange={(e) => setStartingCapital(parseFloat(e.target.value))}
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Fee (bps)</label>
            <input
              type="number"
              value={feeBps}
              onChange={(e) => setFeeBps(parseFloat(e.target.value))}
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Slippage (bps)</label>
            <input
              type="number"
              value={slippageBps}
              onChange={(e) => setSlippageBps(parseFloat(e.target.value))}
              className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Session Filter</label>
          <select
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
          >
            <option value="">All Day (24h)</option>
            <option value="regular">Regular Hours (9:30-16:00 ET)</option>
            <option value="premarket">Premarket (4:00-9:30 ET)</option>
            <option value="afterhours">After Hours (16:00-20:00 ET)</option>
            <option value="custom">Custom Time Window</option>
          </select>
        </div>

        {sessionFilter === "custom" && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Start Time (UTC)</label>
              <input
                type="time"
                value={sessionStart}
                onChange={(e) => setSessionStart(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">End Time (UTC)</label>
              <input
                type="time"
                value={sessionEnd}
                onChange={(e) => setSessionEnd(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white"
              />
            </div>
          </div>
        )}

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white py-3 rounded-lg font-bold disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create Simulation"}
        </button>
      </form>
    </div>
  );
}
