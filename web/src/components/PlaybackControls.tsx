"use client";

interface PlaybackControlsProps {
  isPlaying: boolean;
  speed: number;
  currentIndex: number;
  totalCandles: number;
  isFinished: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStep: () => void;
  onSpeedChange: (speed: number) => void;
}

const SPEEDS = [0.25, 0.5, 1, 2, 5, 10];

export default function PlaybackControls({
  isPlaying,
  speed,
  currentIndex,
  totalCandles,
  isFinished,
  onPlay,
  onPause,
  onStep,
  onSpeedChange,
}: PlaybackControlsProps) {
  const progress = totalCandles > 0 ? (currentIndex / totalCandles) * 100 : 0;

  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-2">
      <div className="flex items-center gap-3">
        <button
          onClick={isPlaying ? onPause : onPlay}
          disabled={isFinished}
          className={`px-4 py-2 rounded font-bold text-sm ${
            isFinished
              ? "bg-gray-600 text-gray-400 cursor-not-allowed"
              : isPlaying
              ? "bg-yellow-600 hover:bg-yellow-500 text-white"
              : "bg-green-600 hover:bg-green-500 text-white"
          }`}
        >
          {isFinished ? "Done" : isPlaying ? "Pause" : "Play"}
        </button>

        <button
          onClick={onStep}
          disabled={isFinished || isPlaying}
          className={`px-3 py-2 rounded text-sm ${
            isFinished || isPlaying
              ? "bg-gray-600 text-gray-400 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 text-white"
          }`}
        >
          Step
        </button>

        <div className="flex items-center gap-1 ml-2">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => onSpeedChange(s)}
              className={`px-2 py-1 rounded text-xs ${
                speed === s
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-400 hover:bg-gray-600"
              }`}
            >
              {s}x
            </button>
          ))}
        </div>

        <div className="ml-auto text-sm text-gray-400 font-mono">
          {currentIndex} / {totalCandles}
        </div>
      </div>

      <div className="w-full bg-gray-700 rounded-full h-1.5">
        <div
          className="bg-blue-500 h-1.5 rounded-full transition-all duration-200"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
