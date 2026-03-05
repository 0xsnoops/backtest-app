"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { createWS, getToken, api } from "@/lib/api";
import { useRoundStore } from "@/lib/store";
import OrderTicket from "@/components/OrderTicket";
import PositionPanel from "@/components/PositionPanel";
import TradeLog from "@/components/TradeLog";
import PlaybackControls from "@/components/PlaybackControls";

const Chart = dynamic(() => import("@/components/Chart"), { ssr: false });

export default function RoundPlayerPage() {
  const router = useRouter();
  const params = useParams();
  const simId = params.simId as string;
  const roundId = params.roundId as string;

  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [startingCapital, setStartingCapital] = useState(10000);

  const {
    candles,
    currentIndex,
    totalCandles,
    isPlaying,
    speed,
    isFinished,
    snapshot,
    fills,
    orders,
    metrics,
    addCandle,
    setSnapshot,
    addFill,
    addOrder,
    setPlaying,
    setSpeed,
    setFinished,
    setProgress,
    reset,
  } = useRoundStore();

  const speedRef = useRef(speed);
  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  const connectWS = useCallback(() => {
    const token = getToken();
    if (!token) {
      router.push("/");
      return;
    }

    const ws = createWS(token);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({
        action: "start",
        sim_id: simId,
        round_id: roundId,
      }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "candle") {
        if (msg.candle) {
          addCandle(msg.candle);
        }
        if (msg.snapshot) {
          setSnapshot(msg.snapshot);
        }
        setProgress(msg.index, msg.total);
      } else if (msg.type === "fill") {
        addFill(msg);
      } else if (msg.type === "finished") {
        setFinished(true, msg.metrics);
      } else if (msg.type === "order_ack") {
        addOrder({
          id: msg.order_id,
          side: msg.side,
          type: "market",
          qty: msg.qty,
          limit_price: null,
          status: "pending",
          ts_index: currentIndex,
        });
      } else if (msg.type === "error") {
        console.error("WS error:", msg.message);
      }
    };

    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
  }, [simId, roundId]);

  useEffect(() => {
    reset();
    // Load simulation to get starting capital
    api.getSimulation(simId).then((sim) => setStartingCapital(sim.starting_capital));
    connectWS();
    return () => {
      wsRef.current?.close();
    };
  }, [simId, roundId, connectWS]);

  const sendAction = (action: string, extra?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...extra }));
    }
  };

  const handlePlay = () => {
    setPlaying(true);
    sendAction("play");
  };

  const handlePause = () => {
    setPlaying(false);
    sendAction("pause");
  };

  const handleStep = () => {
    setPlaying(false);
    sendAction("step");
  };

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed);
    sendAction("speed", { value: newSpeed });
  };

  const handleOrder = (order: { side: string; type: string; qty: number; limit_price: number | null }) => {
    sendAction("order", order);
  };

  const currentPrice = candles.length > 0 ? candles[candles.length - 1].close : undefined;

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.push(`/simulation/${simId}`)}
          className="text-gray-400 hover:text-white text-sm"
        >
          &larr; Back to Rounds
        </button>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`} />
          <span className="text-gray-400 text-xs">
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      <Chart candles={candles} />

      <PlaybackControls
        isPlaying={isPlaying}
        speed={speed}
        currentIndex={currentIndex}
        totalCandles={totalCandles}
        isFinished={isFinished}
        onPlay={handlePlay}
        onPause={handlePause}
        onStep={handleStep}
        onSpeedChange={handleSpeedChange}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <OrderTicket
          onSubmit={handleOrder}
          disabled={isFinished}
          currentPrice={currentPrice}
        />
        <PositionPanel snapshot={snapshot} startingCapital={startingCapital} />
        <TradeLog fills={fills} orders={orders} />
      </div>

      {isFinished && metrics && (
        <div className="bg-gray-800 rounded-xl p-6">
          <h2 className="text-xl font-bold mb-4">Round Complete!</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-400">P&L</span>
              <p className={`text-lg font-bold ${(metrics.pnl_dollar as number) >= 0 ? "text-green-400" : "text-red-400"}`}>
                ${(metrics.pnl_dollar as number)?.toFixed(2)} ({(metrics.pnl_pct as number)?.toFixed(2)}%)
              </p>
            </div>
            <div>
              <span className="text-gray-400">Max Drawdown</span>
              <p className="text-lg font-bold text-red-400">{(metrics.max_drawdown as number)?.toFixed(2)}%</p>
            </div>
            <div>
              <span className="text-gray-400">Win Rate</span>
              <p className="text-lg font-bold text-white">{(metrics.win_rate as number)?.toFixed(1)}%</p>
            </div>
            <div>
              <span className="text-gray-400">Trades</span>
              <p className="text-lg font-bold text-white">{metrics.num_trades as number}</p>
            </div>
            <div>
              <span className="text-gray-400">Avg Win</span>
              <p className="text-lg font-bold text-green-400">${(metrics.avg_win as number)?.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-gray-400">Avg Loss</span>
              <p className="text-lg font-bold text-red-400">${(metrics.avg_loss as number)?.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-gray-400">Profit Factor</span>
              <p className="text-lg font-bold text-white">{(metrics.profit_factor as number)?.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-gray-400">Sharpe</span>
              <p className="text-lg font-bold text-white">{(metrics.sharpe as number)?.toFixed(2)}</p>
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => router.push(`/simulation/${simId}`)}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded font-bold text-sm"
            >
              Next Round
            </button>
            <button
              onClick={() => router.push(`/simulation/${simId}/results`)}
              className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded font-bold text-sm"
            >
              View All Results
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
