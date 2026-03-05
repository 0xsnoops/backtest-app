import { create } from "zustand";

export interface CandleData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Snapshot {
  equity: number;
  cash: number;
  position_qty: number;
  avg_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
}

export interface FillData {
  order_id: string;
  fill_price: number;
  qty: number;
  fee: number;
  side: string;
  ts_index: number;
}

export interface OrderData {
  id: string;
  side: string;
  type: string;
  qty: number;
  limit_price: number | null;
  status: string;
  ts_index: number;
}

interface RoundState {
  candles: CandleData[];
  currentIndex: number;
  totalCandles: number;
  isPlaying: boolean;
  speed: number;
  isFinished: boolean;
  snapshot: Snapshot | null;
  fills: FillData[];
  orders: OrderData[];
  metrics: Record<string, unknown> | null;

  addCandle: (candle: CandleData) => void;
  setSnapshot: (snap: Snapshot) => void;
  addFill: (fill: FillData) => void;
  addOrder: (order: OrderData) => void;
  setPlaying: (playing: boolean) => void;
  setSpeed: (speed: number) => void;
  setFinished: (finished: boolean, metrics?: Record<string, unknown>) => void;
  setProgress: (index: number, total: number) => void;
  reset: () => void;
}

export const useRoundStore = create<RoundState>((set) => ({
  candles: [],
  currentIndex: 0,
  totalCandles: 0,
  isPlaying: false,
  speed: 1,
  isFinished: false,
  snapshot: null,
  fills: [],
  orders: [],
  metrics: null,

  addCandle: (candle) =>
    set((s) => ({ candles: [...s.candles, candle] })),
  setSnapshot: (snapshot) => set({ snapshot }),
  addFill: (fill) =>
    set((s) => ({ fills: [...s.fills, fill] })),
  addOrder: (order) =>
    set((s) => ({ orders: [...s.orders, order] })),
  setPlaying: (isPlaying) => set({ isPlaying }),
  setSpeed: (speed) => set({ speed }),
  setFinished: (isFinished, metrics) => set({ isFinished, metrics: metrics || null, isPlaying: false }),
  setProgress: (currentIndex, totalCandles) => set({ currentIndex, totalCandles }),
  reset: () =>
    set({
      candles: [],
      currentIndex: 0,
      totalCandles: 0,
      isPlaying: false,
      speed: 1,
      isFinished: false,
      snapshot: null,
      fills: [],
      orders: [],
      metrics: null,
    }),
}));

interface AuthState {
  token: string | null;
  user: { id: string; email: string } | null;
  setAuth: (token: string, user: { id: string; email: string }) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: typeof window !== "undefined" ? localStorage.getItem("token") : null,
  user: null,
  setAuth: (token, user) => {
    localStorage.setItem("token", token);
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null });
  },
}));
