"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { api } from "@/lib/api";

interface Round {
  id: string;
  round_number: number;
  status: string;
  current_index: number;
  total_candles: number;
}

interface Simulation {
  id: string;
  symbol: string;
  market: string;
  num_rounds: number;
  starting_capital: number;
  fee_bps: number;
  slippage_bps: number;
  session_filter: string | null;
}

export default function SimulationPage() {
  const router = useRouter();
  const params = useParams();
  const simId = params.simId as string;
  const [sim, setSim] = useState<Simulation | null>(null);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [simData, roundsData] = await Promise.all([
          api.getSimulation(simId),
          api.listRounds(simId),
        ]);
        setSim(simData);
        setRounds(roundsData);
      } catch {
        router.push("/dashboard");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [simId]);

  if (loading || !sim) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  const finishedCount = rounds.filter((r) => r.status === "finished").length;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <button
        onClick={() => router.push("/dashboard")}
        className="text-gray-400 hover:text-white text-sm"
      >
        &larr; Back to Dashboard
      </button>

      <div className="bg-gray-800 rounded-xl p-6">
        <h1 className="text-2xl font-bold mb-2">
          {sim.symbol} Simulation
        </h1>
        <div className="flex gap-4 text-sm text-gray-400">
          <span>{sim.market}</span>
          <span>${sim.starting_capital.toLocaleString()} capital</span>
          <span>{sim.fee_bps}bps fee</span>
          <span>{sim.slippage_bps}bps slippage</span>
          {sim.session_filter && <span className="text-purple-300">{sim.session_filter}</span>}
        </div>
        <div className="mt-2 text-sm text-gray-400">
          Progress: {finishedCount} / {sim.num_rounds} rounds completed
        </div>
      </div>

      {finishedCount > 0 && (
        <button
          onClick={() => router.push(`/simulation/${simId}/results`)}
          className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg font-bold text-sm"
        >
          View Results
        </button>
      )}

      <div className="grid gap-3">
        {rounds.map((rnd) => (
          <div
            key={rnd.id}
            className="bg-gray-800 rounded-lg p-4 flex items-center justify-between border border-gray-700"
          >
            <div>
              <h3 className="font-bold">Round {rnd.round_number}</h3>
              <p className="text-sm text-gray-400">
                Status:{" "}
                <span
                  className={
                    rnd.status === "finished"
                      ? "text-green-400"
                      : rnd.status === "active"
                      ? "text-yellow-400"
                      : "text-gray-400"
                  }
                >
                  {rnd.status}
                </span>
                {rnd.total_candles > 0 && (
                  <span className="ml-2">
                    ({rnd.current_index}/{rnd.total_candles} candles)
                  </span>
                )}
              </p>
            </div>
            <button
              onClick={() => router.push(`/simulation/${simId}/round/${rnd.id}`)}
              className={`px-4 py-2 rounded font-bold text-sm ${
                rnd.status === "finished"
                  ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                  : rnd.status === "active"
                  ? "bg-yellow-600 hover:bg-yellow-500 text-white"
                  : "bg-blue-600 hover:bg-blue-500 text-white"
              }`}
            >
              {rnd.status === "finished" ? "Review" : rnd.status === "active" ? "Continue" : "Start"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
