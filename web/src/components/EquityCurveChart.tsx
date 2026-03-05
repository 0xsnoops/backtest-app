"use client";

import { useEffect, useRef } from "react";
import { createChart, IChartApi, Time } from "lightweight-charts";

interface RoundData {
  round_number: number;
  equity_curve: number[];
}

interface EquityCurveChartProps {
  rounds: RoundData[];
}

const COLORS = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0", "#00BCD4", "#FF5722", "#795548"];

export default function EquityCurveChart({ rounds }: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#1a1a2e" },
        textColor: "#e0e0e0",
      },
      grid: {
        vertLines: { color: "#2a2a4a" },
        horzLines: { color: "#2a2a4a" },
      },
      width: containerRef.current.clientWidth,
      height: 300,
    });

    let offset = 0;
    rounds.forEach((rnd, idx) => {
      if (!rnd.equity_curve?.length) return;
      const series = chart.addLineSeries({
        color: COLORS[idx % COLORS.length],
        lineWidth: 2,
        title: `R${rnd.round_number}`,
      });
      series.setData(
        rnd.equity_curve.map((val, i) => ({
          time: (offset + i) as Time,
          value: val,
        }))
      );
      offset += rnd.equity_curve.length + 5;
    });

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [rounds]);

  return <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />;
}
